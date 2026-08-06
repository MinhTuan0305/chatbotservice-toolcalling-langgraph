from typing import Optional

from langchain_core.tools import tool

from app.db.connection import execute_query


@tool
def search_products(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
) -> list[dict]:
    """
    Tìm kiếm sản phẩm trong database.

    Sử dụng tool này khi người dùng muốn tìm sản phẩm
    theo tên, keyword, category hoặc khoảng giá.

    Args:
        keyword:
            Từ khóa tìm kiếm trong tên sản phẩm.

        category:
            Danh mục sản phẩm.

        min_price:
            Giá tối thiểu.

        max_price:
            Giá tối đa.

    Returns:
        Danh sách sản phẩm phù hợp.
    """

    conditions = []
    params = {}

    if keyword:

        conditions.append(
            "LOWER(name) LIKE LOWER(:keyword)"
        )

        params["keyword"] = (
            f"%{keyword}%"
        )

    if category:

        conditions.append(
            "LOWER(category) = LOWER(:category)"
        )

        params["category"] = category

    if min_price is not None:

        conditions.append(
            "price >= :min_price"
        )

        params["min_price"] = min_price

    if max_price is not None:

        conditions.append(
            "price <= :max_price"
        )

        params["max_price"] = max_price

    where_clause = ""

    if conditions:

        where_clause = (
            "WHERE "
            + " AND ".join(conditions)
        )

    query = f"""
        SELECT
            id,
            name,
            category,
            price
        FROM products
        {where_clause}
        ORDER BY id
        LIMIT 100
    """

    return execute_query(
        query,
        params,
    )