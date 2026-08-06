from langchain_core.tools import tool

from app.db.connection import execute_query


@tool
def get_revenue_by_category(
    status: str = "completed",
) -> list[dict]:
    """
    Tính doanh thu theo từng danh mục sản phẩm.

    Mặc định chỉ tính các đơn hàng completed.

    Args:
        status:
            Trạng thái đơn hàng.
            Mặc định là completed.

    Returns:
        Doanh thu theo từng category.
    """

    query = """
        SELECT
            p.category,

            SUM(
                oi.qty * oi.unit_price
            ) AS revenue

        FROM orders o

        JOIN order_items oi
            ON o.id = oi.order_id

        JOIN products p
            ON oi.product_id = p.id

        WHERE
            o.status = :status

        GROUP BY
            p.category

        ORDER BY
            revenue DESC
    """

    return execute_query(
        query,
        {
            "status": status
        },
    )


@tool
def get_top_customers(
    limit: int = 5,
) -> list[dict]:
    """
    Lấy các khách hàng chi tiêu nhiều nhất.

    Chỉ tính các đơn hàng completed.

    Args:
        limit:
            Số lượng khách hàng cần lấy.
            Mặc định là 5.

    Returns:
        Danh sách top khách hàng.
    """

    if limit < 1:
        limit = 5

    if limit > 100:
        limit = 100

    query = """
        SELECT
            c.id AS customer_id,
            c.name,
            c.city,

            SUM(
                oi.qty * oi.unit_price
            ) AS total_spent

        FROM customers c

        JOIN orders o
            ON c.id = o.customer_id

        JOIN order_items oi
            ON o.id = oi.order_id

        WHERE
            o.status = 'completed'

        GROUP BY
            c.id,
            c.name,
            c.city

        ORDER BY
            total_spent DESC

        LIMIT :limit
    """

    return execute_query(
        query,
        {
            "limit": limit
        },
    )