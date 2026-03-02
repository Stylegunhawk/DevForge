"""Domain templates for ecommerce and saas use cases.

Provides pre-configured schemas with hardcoded distribution parameters.
Templates are designed to be used as-is, not customized.
"""

from typing import Optional

from src.tools.datagen.schema_models import (
    EntitySchema,
    FieldSchema,
    RelationshipSchema,
    SchemaDesign,
)


# =============================================================================
# E-commerce Template
# =============================================================================

def get_ecommerce_template(
    requested_rows: Optional[int] = None,
    customer_count: Optional[int] = None,
    product_count: Optional[int] = None,
    order_count: Optional[int] = None
) -> SchemaDesign:
    """Get e-commerce domain template.
    
    Entities: customers, products, orders
    Relationships: orders -> customers, orders -> products
    
    Default Base (650 rows total):
    - customers: 100
    - products: 50
    - orders: 500
    
    Args:
        requested_rows: Scale total rows proportionally from 650
        customer_count: Explicit override for customers
        product_count: Explicit override for products
        order_count: Explicit override for orders
        
    Returns:
        SchemaDesign for e-commerce domain
    """
    base_rows = {"customers": 100, "products": 50, "orders": 500}
    
    if requested_rows:
        total_base = sum(base_rows.values())
        scale = requested_rows / total_base
        customer_count = customer_count or max(1, round(base_rows["customers"] * scale))
        product_count = product_count or max(1, round(base_rows["products"] * scale))
        order_count = order_count or max(1, round(base_rows["orders"] * scale))
    else:
        customer_count = customer_count or 100
        product_count = product_count or 50
        order_count = order_count or 500
    return SchemaDesign(
        entities={
            "customers": EntitySchema(
                name="customers",
                fields=[
                    FieldSchema(name="name", type="string", faker_provider="name"),
                    FieldSchema(name="email", type="string", faker_provider="email"),
                    FieldSchema(name="phone", type="string", faker_provider="phone_number"),
                    FieldSchema(name="address", type="string", faker_provider="address"),
                    FieldSchema(name="created_at", type="datetime"),
                ],
                count=customer_count,
                primary_key="id"
            ),
            "products": EntitySchema(
                name="products",
                fields=[
                    FieldSchema(name="name", type="string", faker_provider="text"),
                    FieldSchema(name="category", type="string"),
                    FieldSchema(name="price", type="float", distribution="lognormal"),
                    FieldSchema(name="in_stock", type="boolean"),
                    FieldSchema(name="created_at", type="datetime"),
                ],
                count=product_count,
                primary_key="id"
            ),
            "orders": EntitySchema(
                name="orders",
                fields=[
                    FieldSchema(name="customer_id", type="uuid"),
                    FieldSchema(name="product_id", type="uuid"),
                    FieldSchema(name="quantity", type="int"),
                    FieldSchema(name="total_amount", type="float", distribution="lognormal"),
                    FieldSchema(name="status", type="string"),
                    FieldSchema(name="order_date", type="datetime"),
                ],
                count=order_count,
                primary_key="id"
            ),
        },
        relationships=[
            RelationshipSchema(
                from_entity="orders",
                from_field="customer_id",
                to_entity="customers",
                to_field="id",
                cardinality="1:N"
            ),
            RelationshipSchema(
                from_entity="orders",
                from_field="product_id",
                to_entity="products",
                to_field="id",
                cardinality="1:N"
            ),
        ],
        domain="ecommerce"
    )


# =============================================================================
# SaaS Template
# =============================================================================

def get_saas_template(
    requested_rows: Optional[int] = None,
    user_count: Optional[int] = None,
    subscription_count: Optional[int] = None,
    usage_log_count: Optional[int] = None
) -> SchemaDesign:
    """Get SaaS domain template.
    
    Entities: users, subscriptions, usage_logs
    Relationships: subscriptions -> users, usage_logs -> subscriptions
    
    Default Base (1220 rows total):
    - users: 100
    - subscriptions: 120
    - usage_logs: 1000
    
    Args:
        requested_rows: Scale total rows proportionally from 1220
        user_count: Explicit override for users
        subscription_count: Explicit override for subscriptions
        usage_log_count: Explicit override for usage logs
        
    Returns:
        SchemaDesign for SaaS domain
    """
    base_rows = {"users": 100, "subscriptions": 120, "usage_logs": 1000}
    
    if requested_rows:
        total_base = sum(base_rows.values())
        scale = requested_rows / total_base
        user_count = user_count or max(1, round(base_rows["users"] * scale))
        subscription_count = subscription_count or max(1, round(base_rows["subscriptions"] * scale))
        usage_log_count = usage_log_count or max(1, round(base_rows["usage_logs"] * scale))
    else:
        user_count = user_count or 100
        subscription_count = subscription_count or 120
        usage_log_count = usage_log_count or 1000
    return SchemaDesign(
        entities={
            "users": EntitySchema(
                name="users",
                fields=[
                    FieldSchema(name="username", type="string", faker_provider="user_name"),
                    FieldSchema(name="email", type="string", faker_provider="email"),
                    FieldSchema(name="full_name", type="string", faker_provider="name"),
                    FieldSchema(name="created_at", type="datetime"),
                    FieldSchema(name="is_active", type="boolean"),
                ],
                count=user_count,
                primary_key="id"
            ),
            "subscriptions": EntitySchema(
                name="subscriptions",
                fields=[
                    FieldSchema(name="user_id", type="uuid"),
                    FieldSchema(name="plan", type="string", distribution="categorical"),
                    FieldSchema(name="price_monthly", type="float"),
                    FieldSchema(name="started_at", type="datetime"),
                    FieldSchema(name="expires_at", type="datetime", nullable=True),
                    FieldSchema(name="is_active", type="boolean"),
                ],
                count=subscription_count,
                primary_key="id"
            ),
            "usage_logs": EntitySchema(
                name="usage_logs",
                fields=[
                    FieldSchema(name="subscription_id", type="uuid"),
                    FieldSchema(name="action", type="string"),
                    FieldSchema(name="timestamp", type="datetime"),
                    FieldSchema(name="api_calls", type="int", distribution="pareto"),
                    FieldSchema(name="data_mb", type="float", distribution="lognormal"),
                ],
                count=usage_log_count,
                primary_key="id"
            ),
        },
        relationships=[
            RelationshipSchema(
                from_entity="subscriptions",
                from_field="user_id",
                to_entity="users",
                to_field="id",
                cardinality="1:N"
            ),
            RelationshipSchema(
                from_entity="usage_logs",
                from_field="subscription_id",
                to_entity="subscriptions",
                to_field="id",
                cardinality="1:N"
            ),
        ],
        domain="saas"
    )
 
 
# =============================================================================
# IoT Devices Template
# =============================================================================
 
def get_iot_devices_template(
    requested_rows: Optional[int] = None,
    device_count: Optional[int] = None,
    reading_count: Optional[int] = None
) -> SchemaDesign:
    """Get IoT devices domain template.
    
    Entities: devices, readings
    Relationships: readings -> devices
    
    Default Base (1100 rows total):
    - devices: 100
    - readings: 1000
    
    Args:
        requested_rows: Scale total rows proportionally from 1100
        device_count: Explicit override for devices
        reading_count: Explicit override for sensor readings
        
    Returns:
        SchemaDesign for IoT devices domain
    """
    base_rows = {"devices": 100, "readings": 1000}
    
    if requested_rows:
        total_base = sum(base_rows.values())
        scale = requested_rows / total_base
        device_count = device_count or max(1, round(base_rows["devices"] * scale))
        reading_count = reading_count or max(1, round(base_rows["readings"] * scale))
    else:
        device_count = device_count or 100
        reading_count = reading_count or 1000
    return SchemaDesign(
        entities={
            "devices": EntitySchema(
                name="devices",
                fields=[
                    FieldSchema(name="device_name", type="string", faker_provider="name"),
                    FieldSchema(name="model", type="string"),
                    FieldSchema(name="firmware", type="string"),
                    FieldSchema(name="ip_address", type="string", faker_provider="ipv4"),
                    FieldSchema(name="status", type="string"),
                    FieldSchema(name="created_at", type="datetime"),
                ],
                count=device_count,
                primary_key="id"
            ),
            "readings": EntitySchema(
                name="readings",
                fields=[
                    FieldSchema(name="device_id", type="uuid"),
                    FieldSchema(name="sensor_type", type="string"),
                    FieldSchema(name="value", type="float", distribution="normal"),
                    FieldSchema(name="timestamp", type="datetime"),
                ],
                count=reading_count,
                primary_key="id"
            ),
        },
        relationships=[
            RelationshipSchema(
                from_entity="readings",
                from_field="device_id",
                to_entity="devices",
                to_field="id",
                cardinality="1:N"
            ),
        ],
        domain="iot_devices"
    )



# =============================================================================
# Registry and Access
# =============================================================================

# Template registry (only 2 domains for Phase 8.4)
_TEMPLATES = {
    "ecommerce": get_ecommerce_template,
    "saas": get_saas_template,
    "iot_devices": get_iot_devices_template,
}


def get_template(domain: str, **kwargs) -> SchemaDesign:
    """Get a domain template by name.
    
    Args:
        domain: Domain name ("ecommerce", "saas", or "iot_devices")

        **kwargs: Optional overrides for entity counts
        
    Returns:
        SchemaDesign for the specified domain
        
    Raises:
        ValueError: If domain is not recognized
        
    Example:
        >>> schema = get_template("ecommerce")
        >>> schema = get_template("saas", user_count=200)
    """
    domain_lower = domain.lower()
    if domain_lower not in _TEMPLATES:
        available = list(_TEMPLATES.keys())
        raise ValueError(
            f"Unknown domain: '{domain}'. Available domains: {available}"
        )
    
    return _TEMPLATES[domain_lower](**kwargs)


def list_domains() -> list[str]:
    """List all available domain templates.
    
    Returns:
        List of domain names
    """
    return list(_TEMPLATES.keys())
