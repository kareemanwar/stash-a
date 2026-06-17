package sqlite

func init() {
	if appSchemaVersion < 87 {
		appSchemaVersion = 87
	}
}
