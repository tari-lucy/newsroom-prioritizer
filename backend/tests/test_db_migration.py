"""Тесты доводки схемы: create_all не добавляет колонки уже существующим таблицам,
поэтому новые поля доезжают на работающую установку отдельным шагом."""
from database.database import _ADDED_COLUMNS, _add_column_sql, _apply_column_migrations, engine


def test_add_column_sql_is_idempotent():
    sql = _add_column_sql("source", "category", "VARCHAR NOT NULL DEFAULT 'media'")
    assert sql == "ALTER TABLE source ADD COLUMN IF NOT EXISTS category VARCHAR NOT NULL DEFAULT 'media'"


def test_every_migration_is_repeatable():
    # Шаг выполняется при каждом старте API — он обязан быть безопасным на повторе.
    for table, column, definition in _ADDED_COLUMNS:
        assert "IF NOT EXISTS" in _add_column_sql(table, column, definition)


def test_migrations_skipped_on_sqlite():
    # В тестах база создаётся с нуля из моделей: доводить нечего, и падать шаг не должен.
    assert engine.dialect.name == "sqlite"
    _apply_column_migrations()
