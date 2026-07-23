env "local" {
  url = "sqlite://bot.db?_fk=1"
  dev = "sqlite://dev?mode=memory&_fk=1"

  schema {
    src = "file://schema.sql"
  }

  migration {
    dir = "file://migrations"
  }
}
