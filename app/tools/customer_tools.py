from typing import Optional

from langchain_core.tools import tool

from app.db.connection import execute_query


@tool
def get_customer_by_name(
    name: str,
) -> list[dict]:
    """
    Tìm khách hàng theo tên gần đúng.

    Sử dụng khi người dùng cung cấp tên khách hàng
    và muốn tìm thông tin khách hàng.

    Args:
        name:
            Tên khách hàng cần tìm.

    Returns:
        Danh sách khách hàng phù hợp.
        Nếu không tìm thấy thì trả về [].
    """

    query = """
        SELECT
            id,
            name,
            city,
            created_at
        FROM customers
        WHERE LOWER(name) LIKE LOWER(:name)
        ORDER BY id
        LIMIT 20
    """

    return execute_query(
        query,
        {
            "name": f"%{name}%"
        },
    )


@tool
def get_customer_orders(
    customer_id: int,
    status: Optional[str] = None,
) -> list[dict]:
    """
    Lấy danh sách đơn hàng của một khách hàng.

    Tổng tiền mỗi đơn được tính bằng:
    SUM(qty * unit_price).

    Args:
        customer_id:
            ID khách hàng.

        status:
            Trạng thái đơn hàng.
            Nếu không truyền thì lấy tất cả trạng thái.

    Returns:
        Danh sách đơn hàng và tổng tiền.
    """

    status_condition = ""

    params = {
        "customer_id": customer_id
    }

    if status:

        status_condition = """
            AND o.status = :status
        """

        params["status"] = status

    query = f"""
        SELECT
            o.id AS order_id,
            o.customer_id,
            o.order_date,
            o.status,
            o.shipped_date,

            COALESCE(
                SUM(
                    oi.qty * oi.unit_price
                ),
                0
            ) AS total_amount

        FROM orders o

        LEFT JOIN order_items oi
            ON o.id = oi.order_id

        WHERE
            o.customer_id = :customer_id

        {status_condition}

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
        params,
    )