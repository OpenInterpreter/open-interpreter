from abc import ABC, abstractmethod
from typing import Dict, List


class FinalQuery:
    def __init__(self, query):
        self._query = query

    def __repr__(self):
        return f'{self.__class__.__name__}("{self._query}")'


class Query:
    def __init__(self, query: str, columns: List[str]):
        self.query = query
        self.columns = columns

    def __repr__(self):
        return f'{self.__class__.__name__}("{self.query}", columns={self.columns})'

    def select(self, *columns: str):
        if not (set(columns) <= set(self.columns)):
            raise ValueError(
                f"Unknown column names passed: {set(columns) - set(self.columns)}"
            )

        selected_columns = ", ".join(columns)
        return FinalQuery(f"SELECT {selected_columns} FROM {self.query}")

    def select_star(self):
        return FinalQuery(f"SELECT * FROM {self.query}")

    def where(self, where_clause: str):
        return Query(
            f"{self.query} WHERE {where_clause}",
            columns=self.columns,
        )

    def insert_into(self) -> FinalQuery:
        columns = ", ".join(self.columns)
        placeholders = ", ".join(["?"] * len(self.columns))
        return FinalQuery(
            f"INSERT INTO {self.query}({columns}) VALUES ({placeholders})"
        )

    def drop_table(self) -> FinalQuery:
        return FinalQuery(f"DROP TABLE {self.query}")

    def delete_from(self) -> FinalQuery:
        return FinalQuery(f"DELETE FROM {self.query}")


class Model(ABC):
    @property
    @abstractmethod
    def table_name(self) -> str:
        ...

    @property
    @abstractmethod
    def schema(self) -> Dict[str, str]:
        ...

    @classmethod
    def create_table(cls, connection):
        metadata_table = [
            f"{column_name} {column_type}"
            for column_name, column_type in cls.schema.items()
        ]
        metadata_table_definition = ", ".join(metadata_table)
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS {cls.table_name}({metadata_table_definition})"
        )


class Name(Model):
    table_name = "names"
    schema = {
        "name": "TEXT",
        "module": "TEXT",
        "package": "TEXT",
        "source": "INTEGER",
        "type": "INTEGER",
    }
    columns = list(schema.keys())
    objects = Query(table_name, columns)

    @classmethod
    def create_table(cls, connection):
        super().create_table(connection)
        connection.execute("CREATE INDEX IF NOT EXISTS name ON names(name)")
        connection.execute("CREATE INDEX IF NOT EXISTS module ON names(module)")
        connection.execute("CREATE INDEX IF NOT EXISTS package ON names(package)")

    search_submodule_like = objects.where('module LIKE ("%." || ?)')
    search_module_like = objects.where("module LIKE (?)")

    import_assist = objects.where("name LIKE (? || '%')")

    search_by_name_like = objects.where("name LIKE (?)")

    delete_by_module_name = objects.where("module = ?").delete_from()


class Package(Model):
    table_name = "packages"
    schema = {
        "package": "TEXT",
        "path": "TEXT",
    }
    columns = list(schema.keys())
    objects = Query(table_name, columns)

    delete_by_package_name = objects.where("package = ?").delete_from()
