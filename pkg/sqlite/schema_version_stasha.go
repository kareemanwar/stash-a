package sqlite

func init() {
	if appSchemaVersion < 88 {
		appSchemaVersion = 88
	}
}
