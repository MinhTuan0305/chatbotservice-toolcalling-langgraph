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

@tool
def get_orders_by_status(
    status: str,
) -> list[dict]:
    """
    Lấy danh sách các đơn hàng theo trạng thái.

    Các trạng thái hợp lệ:
    - pending: đang chờ xử lý
    - completed: đã hoàn thành
    - cancelled: đã hủy

    Args:
        status:
            Trạng thái đơn hàng cần tìm.

    Returns:
        Danh sách các đơn hàng có trạng thái tương ứng.
    """

    query = """
        SELECT
            o.id AS order_id,
            o.customer_id,
            o.order_date,
            o.status,
            o.shipped_date,


            SUM(
                oi.qty * oi.unit_price
            ) AS order_total

        FROM orders o

        JOIN order_items oi
            ON o.id = oi.order_id

        WHERE
            o.status = :status

        GROUP BY
            o.id,
            o.customer_id,
            o.order_date,
            o.status,
            o.shipped_date

        ORDER BY
            o.order_date DESC
    """

    return execute_query(
        query,
        {
            "status": status
        },
    )

@tool
def get_total_order_amount_by_status(
    status: str,
) -> dict:
    """
    Tính tổng giá trị đơn hàng
    theo trạng thái.
    """

    query = """
        SELECT
            COUNT(DISTINCT o.id) AS order_count,

            COALESCE(SUM(oi.qty * oi.unit_price), 0) AS total_amount

        FROM orders o

        LEFT JOIN order_items oi ON o.id = oi.order_id

        WHERE
            o.status = :status
    """

    result = execute_query(
        query,
        {
            "status": status,
        },
    )

    return result[0] if result else {
        "order_count": 0,
        "total_amount": 0,
    }