from sqlalchemy import create_engine, text

from app.config import DATABASE_URL


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


def execute_query(
    query: str,
    params: dict | None = None,
) -> list[dict]:
    """
    Thực hiện SELECT query và trả về
    danh sách dictionary.

    Chỉ cho phép các truy vấn SELECT.
    """

    normalized_query = query.strip().lower()

    if not normalized_query.startswith("select"):
        raise ValueError(
            "Chỉ cho phép thực hiện SELECT query."
        )

    with engine.connect() as connection:

        result = connection.execute(
            text(query),
            params or {},
        )

        return [
            dict(row._mapping)
            for row in result
        ]


if __name__ == "__main__":

    result = execute_query(
        """
        SELECT *
        FROM products
        LIMIT 5
        """
    )

    for row in result:
        print(row)