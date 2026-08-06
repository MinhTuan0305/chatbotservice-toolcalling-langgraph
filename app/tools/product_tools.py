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

@tool
def get_unsold_products(
    category: Optional[str] = None,
) -> list[dict]:
    """
    Lấy danh sách các sản phẩm chưa từng được bán.

    Một sản phẩm được coi là "chưa từng bán"
    khi nó không xuất hiện trong bất kỳ order_items
    nào thuộc đơn hàng KHÔNG bị hủy (status != 'cancelled').

    Nói cách khác: nếu sản phẩm chỉ từng nằm trong
    các đơn đã hủy thì vẫn được tính là chưa bán được.

    Sử dụng khi người dùng hỏi về:
    - Sản phẩm chưa bán được / ế / tồn kho chưa ai mua.
    - Sản phẩm chưa từng có trong đơn hàng nào.
    - Kiểm tra hiệu quả bán hàng theo category.

    Args:
        category:
            Danh mục sản phẩm để lọc.
            Nếu không truyền thì lấy tất cả danh mục.

    Returns:
        Danh sách sản phẩm chưa bán được, gồm:
        - id
        - name
        - category
        - price
    """

    conditions = [
        "o.id IS NULL",
    ]

    params = {}

    if category:
        conditions.append("LOWER(p.category) = LOWER(:category)")
        params["category"] = category

    where_clause = " AND ".join(conditions)

    query = f"""
    SELECT
        p.id,
        p.name,
        p.category,
        p.price

    FROM products p

    LEFT JOIN order_items oi
        ON p.id = oi.product_id

    LEFT JOIN orders o
        ON oi.order_id = o.id
        AND o.status != 'canceled'

    WHERE
        {where_clause}
    
    ORDER BY
        p.id

    """

    return execute_query(
        query,
        params,
    )
    
