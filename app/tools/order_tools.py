from langchain_core.tools import tool

from app.db.connection import execute_query

from typing import Optional


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

@tool
def get_pending_orders(
    customer_id: Optional[int] = None,
    min_days_since_order: Optional[int] = None,
) -> list[dict]:
    """
    Lấy danh sách các đơn hàng chưa được giao.

    Một đơn hàng được coi là "chưa giao"
    khi shipped_date là NULL và trạng thái
    khác 'cancelled'.

    Lưu ý: khác với get_orders_by_status(status="pending"),
    tool này KHÔNG lọc theo cột status mà lọc theo
    việc đơn đã có ngày giao hàng hay chưa. Nghĩa là
    các đơn có status = 'completed' nhưng shipped_date
    vẫn NULL cũng sẽ được trả về.

    Sử dụng khi người dùng hỏi về:
    - Đơn hàng chưa giao / chưa ship / đang chờ giao.
    - Đơn hàng bị trễ giao (kết hợp với
      min_days_since_order).

    Args:
        customer_id:
            ID khách hàng để lọc.
            Nếu không truyền thì lấy tất cả khách hàng.

        min_days_since_order:
            Số ngày tối thiểu kể từ ngày đặt hàng
            (order_date) đến hiện tại.
            Dùng để tìm các đơn bị trễ giao lâu ngày.
            Nếu không truyền thì không lọc theo thời gian.

    Returns:
        Danh sách đơn hàng chưa giao, gồm:
        - order_id
        - customer_id
        - order_date
        - status
        - days_since_order: số ngày kể từ khi đặt hàng.
        - order_total: tổng tiền đơn hàng.
    """

    conditions = [
        "o.shipped_date IS NULL",
        "o.status != 'cancelled'",
    ]

    params = {}

    if customer_id is not None:

        conditions.append(
            "o.customer_id = :customer_id"
        )

        params["customer_id"] = customer_id

    if min_days_since_order is not None:

        conditions.append(
            "(CURRENT_DATE - o.order_date) >= :min_days_since_order"
        )

        params["min_days_since_order"] = min_days_since_order

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            o.id AS order_id,
            o.customer_id,
            o.order_date,
            o.status,

            (CURRENT_DATE - o.order_date) AS days_since_order,

            COALESCE(
                SUM(
                    oi.qty * oi.unit_price
                ),
                0
            ) AS order_total

        FROM orders o

        LEFT JOIN order_items oi
            ON o.id = oi.order_id

        WHERE
            {where_clause}

        GROUP BY
            o.id,
            o.customer_id,
            o.order_date,
            o.status

        ORDER BY
            o.order_date ASC
    """

    return execute_query(
        query,
        params,
    )