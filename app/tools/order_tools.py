from langchain_core.tools import tool

from app.db.connection import execute_query


@tool
def get_order_detail(
    order_id: int,
) -> list[dict]:
    """
    Lấy thông tin chi tiết của một đơn hàng.

    Bao gồm thông tin đơn hàng và sản phẩm
    trong đơn hàng.

    Nếu shipped_date là NULL,
    đơn hàng chưa được giao.

    Args:
        order_id:
            ID đơn hàng.

    Returns:
        Chi tiết đơn hàng và sản phẩm.
    """

    query = """
        SELECT
            o.id AS order_id,
            o.customer_id,
            o.order_date,
            o.status,
            o.shipped_date,

            oi.id AS order_item_id,
            oi.product_id,

            p.name AS product_name,

            oi.qty,
            oi.unit_price,

            (
                oi.qty * oi.unit_price
            ) AS item_total

        FROM orders o

        LEFT JOIN order_items oi
            ON o.id = oi.order_id

        LEFT JOIN products p
            ON oi.product_id = p.id

        WHERE
            o.id = :order_id

        ORDER BY
            oi.id
    """

    return execute_query(
        query,
        {
            "order_id": order_id
        },
    )