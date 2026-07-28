from app.tools.product_tools import (
    search_products,
)

from app.tools.customer_tools import (
    get_customer_by_name,
    get_customer_orders,
)

from app.tools.order_tools import (
    get_order_detail,
)

from app.tools.revenue_tools import (
    get_revenue_by_category,
    get_top_customers,
)


ALL_TOOLS = [
    search_products,
    get_customer_by_name,
    get_customer_orders,
    get_order_detail,
    get_revenue_by_category,
    get_top_customers,
]