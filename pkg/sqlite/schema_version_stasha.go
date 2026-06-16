package sqlite

func init() {
	if appSchemaVersion < 86 {
		appSchemaVersion = 86
	}
}
