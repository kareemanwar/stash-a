package sqlite

import (
	"context"
	"database/sql"
	"embed"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/jmoiron/sqlx"

	"github.com/stashapp/stash/pkg/fsutil"
	"github.com/stashapp/stash/pkg/logger"
)

const (
	maxWriteConnections = 1
	// Number of database read connections to use
	maxReadConnections = 10
	// Idle connection timeout, in seconds
	// Closes a connection after a period of inactivity, which saves on memory and
	// causes the sqlite -wal and -shm files to be automatically deleted.
	dbConnTimeout = 30 * time.Second

	// environment variable to set the cache size
	cacheSizeEnv = "STASH_SQLITE_CACHE_SIZE"
)

var appSchemaVersion uint = 85

//go:embed migrations/*.sql
var migrationsBox embed.FS

var (
	// ErrDatabaseNotInitialized indicates that the database is not
	// initialized, usually due to an incomplete configuration.
	ErrDatabaseNotInitialized = errors.New("database not initialized")
)

// ErrMigrationNeeded indicates that a database migration is needed
// before the database can be initialized
type MigrationNeededError struct {
	CurrentSchemaVersion  uint
	RequiredSchemaVersion uint
}

func (e *MigrationNeededError) Error() string {
	return fmt.Sprintf("database schema version %d does not match required schema version %d", e.CurrentSchemaVersion, e.RequiredSchemaVersion)
}

type MismatchedSchemaVersionError struct {
	CurrentSchemaVersion  uint
	RequiredSchemaVersion uint
}

func (e *MismatchedSchemaVersionError) Error() string {
	return fmt.Sprintf("schema version %d is incompatible with required schema version %d", e.CurrentSchemaVersion, e.RequiredSchemaVersion)
}

type storeRepository struct {
	Blobs            *BlobStore
	File             *FileStore
	Folder           *FolderStore
	Image            *ImageStore
	Gallery          *GalleryStore
	GalleryChapter   *GalleryChapterStore
	Scene            *SceneStore
	SceneMarker      *SceneMarkerStore
	SceneOnlineMedia *SceneOnlineMediaStore
	Source           *SourceStore
	Performer        *PerformerStore
	SavedFilter      *SavedFilterStore
	Studio           *StudioStore
	Tag              *TagStore
	Group            *GroupStore
}

type Database struct {
	*storeRepository

	readDB  *sqlx.DB
	writeDB *sqlx.DB
	dbPath  string

	schemaVersion uint

	lockChan chan struct{}
}

func NewDatabase() *Database {
	fileStore := NewFileStore()
	folderStore := NewFolderStore()
	galleryStore := NewGalleryStore(fileStore, folderStore)
	blobStore := NewBlobStore(BlobStoreOptions{})
	performerStore := NewPerformerStore(blobStore)
	studioStore := NewStudioStore(blobStore)
	tagStore := NewTagStore(blobStore)

	r := &storeRepository{}
	*r = storeRepository{
		Blobs:            blobStore,
		File:             fileStore,
		Folder:           folderStore,
		Scene:            NewSceneStore(r, blobStore),
		SceneMarker:      NewSceneMarkerStore(),
		SceneOnlineMedia: NewSceneOnlineMediaStore(),
		Source:           NewSourceStore(),
		Image:            NewImageStore(r),
		Gallery:          galleryStore,
		GalleryChapter:   NewGalleryChapterStore(),
		Performer:        performerStore,
		Studio:           studioStore,
		Tag:              tagStore,
		Group:            NewGroupStore(blobStore),
		SavedFilter:      NewSavedFilterStore(),
	}

	ret := &Database{
		storeRepository: r,
		lockChan:        make(chan struct{}, 1),
	}

	return ret
}

func (db *Database) SetBlobStoreOptions(options BlobStoreOptions) {
	*db.Blobs = *NewBlobStore(options)
}

// Ready returns an error if the database is not ready to begin transactions.
func (db *Database) Ready() error {
	if db.readDB == nil || db.writeDB == nil {
		return ErrDatabaseNotInitialized
	}

	return nil
}

// Open initializes the database. If the database is new, then it
// performs a full migration to the latest schema version. Otherwise, any
// necessary migrations must be run separately using RunMigrations.
// Returns true if the database is new.
func (db *Database) Open(dbPath string) error {
	db.lock()
	defer db.unlock()

	db.dbPath = dbPath

	databaseSchemaVersion, err := db.getDatabaseSchemaVersion()
	if err != nil {
		return fmt.Errorf("getting database schema version: %w", err)
	}

	db.schemaVersion = databaseSchemaVersion

	isNew := databaseSchemaVersion == 0

	if isNew {
		// new database, just run the migrations
		if err := db.RunAllMigrations(); err != nil {
			return fmt.Errorf("error running initial schema migrations: %w", err)
		}
	} else {
		if databaseSchemaVersion > appSchemaVersion {
			return &MismatchedSchemaVersionError{
				CurrentSchemaVersion:  databaseSchemaVersion,
				RequiredSchemaVersion: appSchemaVersion,
			}
		}

		// if migration is needed, then don't open the connection
		if db.needsMigration() {
			return &MigrationNeededError{
				CurrentSchemaVersion:  databaseSchemaVersion,
				RequiredSchemaVersion: appSchemaVersion,
			}
		}
	}

	if err := db.initialise(); err != nil {
		return err
	}

	if isNew {
		// optimize database after migration
		err = db.Optimise(context.Background())
		if err != nil {
			logger.Warnf("error while performing post-migration optimisation: %v", err)
		}
	}

	return nil
}

// lock locks the database for writing. This method will block until the lock is acquired.
func (db *Database) lock() {
	db.lockChan <- struct{}{}
}

// unlock unlocks the database
func (db *Database) unlock() {
	// will block the caller if the lock is not held, so check first
	select {
	case <-db.lockChan:
		return
	default:
		panic("database is not locked")
	}
}

func (db *Database) Close() error {
	db.lock()
	defer db.unlock()

	if db.readDB != nil {
		if err := db.readDB.Close(); err != nil {
			return err
		}
	}
	if db.writeDB != nil {
		if err := db.writeDB.Close(); err != nil {
			return err
		}
	}

	return nil
}
