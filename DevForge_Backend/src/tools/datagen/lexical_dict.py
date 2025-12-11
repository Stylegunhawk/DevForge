"""Lexical dictionary for fast field name → semantic type lookup.

Contains 100+ common field name patterns mapped to SemanticType values.
Case-insensitive matching is applied at lookup time.
"""

from src.tools.datagen.semantic_types import SemanticType

# Field name → Semantic type mappings (keys are lowercase for case-insensitive matching)
LEXICAL_DICT: dict[str, SemanticType] = {
    
    # === EMAIL FIELDS ===
    "email": SemanticType.EMAIL_ADDRESS,
    "email_address": SemanticType.EMAIL_ADDRESS,
    "user_email": SemanticType.EMAIL_ADDRESS,
    "customer_email": SemanticType.EMAIL_ADDRESS,
    "contact_email": SemanticType.EMAIL_ADDRESS,
    "work_email": SemanticType.EMAIL_ADDRESS,
    "personal_email": SemanticType.EMAIL_ADDRESS,
    
    # === PHONE FIELDS ===
    "phone": SemanticType.PHONE_NUMBER,
    "phone_number": SemanticType.PHONE_NUMBER,
    "mobile": SemanticType.PHONE_NUMBER,
    "mobile_number": SemanticType.PHONE_NUMBER,
    "telephone": SemanticType.PHONE_NUMBER,
    "cell": SemanticType.PHONE_NUMBER,
    "contact_number": SemanticType.PHONE_NUMBER,
    "fax": SemanticType.PHONE_NUMBER,
    
    # === PERSON NAME FIELDS ===
    "first_name": SemanticType.PERSON_FIRST_NAME,
    "firstname": SemanticType.PERSON_FIRST_NAME,
    "given_name": SemanticType.PERSON_FIRST_NAME,
    "forename": SemanticType.PERSON_FIRST_NAME,
    
    "last_name": SemanticType.PERSON_LAST_NAME,
    "lastname": SemanticType.PERSON_LAST_NAME,
    "surname": SemanticType.PERSON_LAST_NAME,
    "family_name": SemanticType.PERSON_LAST_NAME,
    
    # "name": SemanticType.PERSON_FULL_NAME,  # Removed to allow context-based classification (e.g. product.name)
    "full_name": SemanticType.PERSON_FULL_NAME,
    "customer_name": SemanticType.PERSON_FULL_NAME,
    "user_name": SemanticType.PERSON_FULL_NAME,
    "contact_name": SemanticType.PERSON_FULL_NAME,
    "author_name": SemanticType.PERSON_FULL_NAME,
    "employee_name": SemanticType.PERSON_FULL_NAME,
    
    # === COMPANY/ORGANIZATION FIELDS ===
    "company": SemanticType.COMPANY_NAME,
    "company_name": SemanticType.COMPANY_NAME,
    "business_name": SemanticType.COMPANY_NAME,
    "organization": SemanticType.COMPANY_NAME,
    "organization_name": SemanticType.COMPANY_NAME,
    "org_name": SemanticType.COMPANY_NAME,
    "employer": SemanticType.COMPANY_NAME,
    "vendor": SemanticType.COMPANY_NAME,
    "vendor_name": SemanticType.COMPANY_NAME,
    "supplier": SemanticType.COMPANY_NAME,
    "supplier_name": SemanticType.COMPANY_NAME,
    
    # === INSTITUTION FIELDS ===
    "institution": SemanticType.INSTITUTION_NAME,
    "institution_name": SemanticType.INSTITUTION_NAME,
    "university": SemanticType.INSTITUTION_NAME,
    "university_name": SemanticType.INSTITUTION_NAME,
    "school": SemanticType.INSTITUTION_NAME,
    "school_name": SemanticType.INSTITUTION_NAME,
    "college": SemanticType.INSTITUTION_NAME,
    "hospital": SemanticType.INSTITUTION_NAME,
    "bank_name": SemanticType.INSTITUTION_NAME,
    
    # === PRODUCT FIELDS ===
    "product": SemanticType.PRODUCT_NAME,
    "product_name": SemanticType.PRODUCT_NAME,
    "item_name": SemanticType.PRODUCT_NAME,
    "item": SemanticType.PRODUCT_NAME,
    "sku": SemanticType.IDENTIFIER_CODE,
    "sku_name": SemanticType.IDENTIFIER_CODE,
    "article_name": SemanticType.PRODUCT_NAME,
    
    # === DOMAIN-SPECIFIC ENTITIES ===
    "flower": SemanticType.FLOWER_NAME,
    "flower_name": SemanticType.FLOWER_NAME,
    "plant_name": SemanticType.FLOWER_NAME,
    "species": SemanticType.FLOWER_NAME,
    
    # === LOCATION FIELDS ===
    "country": SemanticType.COUNTRY_NAME,
    "country_name": SemanticType.COUNTRY_NAME,
    "nation": SemanticType.COUNTRY_NAME,
    
    "city": SemanticType.CITY_NAME,
    "city_name": SemanticType.CITY_NAME,
    "town": SemanticType.CITY_NAME,
    
    "zip": SemanticType.ZIP_CODE,
    "zip_code": SemanticType.ZIP_CODE,
    "postal": SemanticType.ZIP_CODE,
    "postal_code": SemanticType.ZIP_CODE,
    "postcode": SemanticType.ZIP_CODE,
    
    "lat": SemanticType.GEO_COORDINATE,
    "latitude": SemanticType.GEO_COORDINATE,
    "lng": SemanticType.GEO_COORDINATE,
    "longitude": SemanticType.GEO_COORDINATE,
    "coordinates": SemanticType.GEO_COORDINATE,
    
    # === IDENTIFIER FIELDS ===
    "id": SemanticType.UUID,
    "uuid": SemanticType.UUID,
    "guid": SemanticType.UUID,
    "unique_id": SemanticType.UUID,
    
    "account_number": SemanticType.BANK_ACCOUNT_NUMBER,
    "accountnumber": SemanticType.BANK_ACCOUNT_NUMBER,
    "account_no": SemanticType.BANK_ACCOUNT_NUMBER,
    "iban": SemanticType.BANK_ACCOUNT_NUMBER,
    "routing_number": SemanticType.BANK_ACCOUNT_NUMBER,
    
    "transaction_id": SemanticType.TRANSACTION_ID,
    "txn_id": SemanticType.TRANSACTION_ID,
    "tx_id": SemanticType.TRANSACTION_ID,
    "payment_id": SemanticType.TRANSACTION_ID,
    "reference_number": SemanticType.TRANSACTION_ID,
    "ref_no": SemanticType.TRANSACTION_ID,
    "confirmation_number": SemanticType.TRANSACTION_ID,
    
    "order_id": SemanticType.ORDER_CODE,
    "order_number": SemanticType.ORDER_CODE,
    "order_no": SemanticType.ORDER_CODE,
    "order_code": SemanticType.ORDER_CODE,
    "invoice_number": SemanticType.ORDER_CODE,
    "invoice_no": SemanticType.ORDER_CODE,
    
    "numeric_id": SemanticType.NUMERIC_ID,
    "sequence_number": SemanticType.NUMERIC_ID,
    "seq_no": SemanticType.NUMERIC_ID,
    
    # === MONEY/FINANCIAL FIELDS ===
    "balance": SemanticType.MONEY_AMOUNT,
    "amount": SemanticType.MONEY_AMOUNT,
    "price": SemanticType.MONEY_AMOUNT,
    "total": SemanticType.MONEY_AMOUNT,
    "cost": SemanticType.MONEY_AMOUNT,
    "fee": SemanticType.MONEY_AMOUNT,
    "salary": SemanticType.MONEY_AMOUNT,
    "revenue": SemanticType.MONEY_AMOUNT,
    "income": SemanticType.MONEY_AMOUNT,
    "expense": SemanticType.MONEY_AMOUNT,
    "payment": SemanticType.MONEY_AMOUNT,
    "deposit": SemanticType.MONEY_AMOUNT,
    "withdrawal": SemanticType.MONEY_AMOUNT,
    "subtotal": SemanticType.MONEY_AMOUNT,
    "grand_total": SemanticType.MONEY_AMOUNT,
    "unit_price": SemanticType.MONEY_AMOUNT,
    
    # === PERCENTAGE FIELDS ===
    "percentage": SemanticType.PERCENTAGE,
    "percent": SemanticType.PERCENTAGE,
    "discount": SemanticType.PERCENTAGE,
    "discount_rate": SemanticType.PERCENTAGE,
    "tax_rate": SemanticType.PERCENTAGE,
    "interest_rate": SemanticType.PERCENTAGE,
    "rate": SemanticType.PERCENTAGE,
    "commission": SemanticType.PERCENTAGE,
    "margin": SemanticType.PERCENTAGE,
    
    # === DATE/TIME FIELDS ===
    "created_at": SemanticType.TIMESTAMP,
    "updated_at": SemanticType.TIMESTAMP,
    "modified_at": SemanticType.TIMESTAMP,
    "deleted_at": SemanticType.TIMESTAMP,
    "last_login": SemanticType.TIMESTAMP,
    "login_time": SemanticType.TIMESTAMP,
    "timestamp": SemanticType.TIMESTAMP,
    "datetime": SemanticType.TIMESTAMP,
    "created_date": SemanticType.TIMESTAMP,
    
    "date": SemanticType.DATE,
    "birth_date": SemanticType.DATE,
    "birthdate": SemanticType.DATE,
    "dob": SemanticType.DATE,
    "start_date": SemanticType.DATE,
    "end_date": SemanticType.DATE,
    "due_date": SemanticType.DATE,
    "expiry_date": SemanticType.DATE,
    "expiration_date": SemanticType.DATE,
    "hire_date": SemanticType.DATE,
    "order_date": SemanticType.DATE,
    "ship_date": SemanticType.DATE,
    
    # === BOOLEAN FIELDS ===
    "is_active": SemanticType.BOOLEAN_FLAG,
    "is_verified": SemanticType.BOOLEAN_FLAG,
    "is_enabled": SemanticType.BOOLEAN_FLAG,
    "is_deleted": SemanticType.BOOLEAN_FLAG,
    "is_admin": SemanticType.BOOLEAN_FLAG,
    "is_premium": SemanticType.BOOLEAN_FLAG,
    "is_published": SemanticType.BOOLEAN_FLAG,
    "is_approved": SemanticType.BOOLEAN_FLAG,
    "has_subscription": SemanticType.BOOLEAN_FLAG,
    "has_verified_email": SemanticType.BOOLEAN_FLAG,
    "can_login": SemanticType.BOOLEAN_FLAG,
    "can_edit": SemanticType.BOOLEAN_FLAG,
    "active": SemanticType.BOOLEAN_FLAG,
    "enabled": SemanticType.BOOLEAN_FLAG,
    "verified": SemanticType.BOOLEAN_FLAG,
    "approved": SemanticType.BOOLEAN_FLAG,
    
    # === ENUM/STATUS FIELDS ===
    "status": SemanticType.ENUM_VALUE,
    "state": SemanticType.ENUM_VALUE,
    "type": SemanticType.ENUM_VALUE,
    "category": SemanticType.ENUM_VALUE,
    "role": SemanticType.ENUM_VALUE,
    "tier": SemanticType.ENUM_VALUE,
    "level": SemanticType.ENUM_VALUE,
    "priority": SemanticType.ENUM_VALUE,
    "gender": SemanticType.ENUM_VALUE,
    "plan": SemanticType.ENUM_VALUE,
    "subscription_type": SemanticType.ENUM_VALUE,
    
    # === FREE TEXT FIELDS ===
    "description": SemanticType.FREE_TEXT,
    "notes": SemanticType.FREE_TEXT,
    "comment": SemanticType.FREE_TEXT,
    "comments": SemanticType.FREE_TEXT,
    "bio": SemanticType.FREE_TEXT,
    "biography": SemanticType.FREE_TEXT,
    "summary": SemanticType.FREE_TEXT,
    "message": SemanticType.FREE_TEXT,
    "content": SemanticType.FREE_TEXT,
    "body": SemanticType.FREE_TEXT,
    "text": SemanticType.FREE_TEXT,
    "remarks": SemanticType.FREE_TEXT,
    "feedback": SemanticType.FREE_TEXT,
    
    # === TECH/WEB FIELDS ===
    "ip": SemanticType.IP_ADDRESS,
    "ip_address": SemanticType.IP_ADDRESS,
    "url": SemanticType.URL,
    "website": SemanticType.URL,
    "website_url": SemanticType.URL,
    "site_url": SemanticType.URL,
    "link": SemanticType.URL,
    "homepage": SemanticType.URL,
    "blog": SemanticType.URL,
    
    # === SYSTEM/DEV FIELDS ===
    "username": SemanticType.USERNAME,
    "login": SemanticType.USERNAME,
    "user_id": SemanticType.NUMERIC_ID,
    "uid": SemanticType.UUID,
    "session_id": SemanticType.UUID,
    "token": SemanticType.UUID,
    "auth_token": SemanticType.UUID,
    "api_key": SemanticType.UUID,
    "client_id": SemanticType.UUID,
    "client_secret": SemanticType.UUID,
    "version": SemanticType.FREE_TEXT,
    "build_number": SemanticType.NUMERIC_ID,
    "commit_hash": SemanticType.FREE_TEXT,
    "hash": SemanticType.FREE_TEXT,
    "checksum": SemanticType.FREE_TEXT,
    "environment": SemanticType.ENUM_VALUE,
    "env": SemanticType.ENUM_VALUE,
    "log_level": SemanticType.ENUM_VALUE,
    "severity": SemanticType.ENUM_VALUE,
    "platform": SemanticType.ENUM_VALUE,
    "os": SemanticType.ENUM_VALUE,
    "browser": SemanticType.ENUM_VALUE,
    "device": SemanticType.ENUM_VALUE,
    "user_agent": SemanticType.USER_AGENT,
    "ip_v4": SemanticType.IP_ADDRESS,
    "ip_v6": SemanticType.IP_V6,
    "mac_address": SemanticType.MAC_ADDRESS,
    "port": SemanticType.NUMERIC_ID,
    "protocol": SemanticType.ENUM_VALUE,
    "method": SemanticType.ENUM_VALUE,
    "status_code": SemanticType.ENUM_VALUE,
    
    # === RETAIL/INVENTORY ===
    "brand": SemanticType.COMPANY_NAME,
    "manufacturer": SemanticType.COMPANY_NAME,
    "model": SemanticType.PRODUCT_NAME,
    "category_id": SemanticType.NUMERIC_ID,
    "subcategory": SemanticType.ENUM_VALUE,
    "department": SemanticType.ENUM_VALUE,
    "aisle": SemanticType.ENUM_VALUE,
    "shelf": SemanticType.FREE_TEXT,
    "bin": SemanticType.FREE_TEXT,
    "stock_level": SemanticType.NUMERIC_ID,
    "quantity": SemanticType.NUMERIC_ID,
    "qty": SemanticType.NUMERIC_ID,
    "inventory": SemanticType.NUMERIC_ID,
    "shipping_method": SemanticType.ENUM_VALUE,
    "shipping_cost": SemanticType.MONEY_AMOUNT,
    "tax": SemanticType.MONEY_AMOUNT,
    "vat": SemanticType.MONEY_AMOUNT,
    "currency": SemanticType.CURRENCY_CODE,
    "currency_code": SemanticType.CURRENCY_CODE,
    "coupon_code": SemanticType.FREE_TEXT,
    "promo_code": SemanticType.FREE_TEXT,
    "tracking_number": SemanticType.FREE_TEXT,
    "rating": SemanticType.NUMERIC_ID,
    "stars": SemanticType.NUMERIC_ID,
    "review_count": SemanticType.NUMERIC_ID,
    
    # === DEMOGRAPHICS ===
    "age": SemanticType.NUMERIC_ID,
    "gender": SemanticType.ENUM_VALUE,
    "sex": SemanticType.ENUM_VALUE,
    "marital_status": SemanticType.ENUM_VALUE,
    "occupation": SemanticType.JOB_TITLE,
    "job_title": SemanticType.JOB_TITLE,
    "nationality": SemanticType.COUNTRY_NAME,
    "language": SemanticType.ENUM_VALUE,
    "locale": SemanticType.ENUM_VALUE,
    "timezone": SemanticType.ENUM_VALUE,
    "ssn": SemanticType.FREE_TEXT,
    "social_security": SemanticType.FREE_TEXT,
    "passport_number": SemanticType.FREE_TEXT,
    "driver_license": SemanticType.FREE_TEXT,
    "education": SemanticType.ENUM_VALUE,
    "degree": SemanticType.ENUM_VALUE,
    "income": SemanticType.MONEY_AMOUNT,
    "salary": SemanticType.MONEY_AMOUNT,
    "net_worth": SemanticType.MONEY_AMOUNT,
    "credit_score": SemanticType.NUMERIC_ID,
    
    # === ADDRESS/GEO ===
    "street": SemanticType.STREET_ADDRESS,
    "street_address": SemanticType.STREET_ADDRESS,
    "address_line_1": SemanticType.STREET_ADDRESS,
    "address_line_2": SemanticType.STREET_ADDRESS,
    "building_number": SemanticType.FREE_TEXT,
    "unit": SemanticType.FREE_TEXT,
    "apt": SemanticType.FREE_TEXT,
    "suite": SemanticType.FREE_TEXT,
    "floor": SemanticType.NUMERIC_ID,
    "district": SemanticType.CITY_NAME,
    "county": SemanticType.CITY_NAME,
    "province": SemanticType.CITY_NAME,
    "region": SemanticType.CITY_NAME,
    "continent": SemanticType.ENUM_VALUE,
    "timezone_offset": SemanticType.FREE_TEXT,
    
    # === FINANCE ===
    "card_number": SemanticType.CREDIT_CARD,
    "credit_card": SemanticType.CREDIT_CARD,
    "cc_number": SemanticType.CREDIT_CARD,
    "cvv": SemanticType.NUMERIC_ID,
    "cvc": SemanticType.NUMERIC_ID,
    "expiration": SemanticType.DATE,
    "exp_date": SemanticType.DATE,
    "routing_number": SemanticType.FREE_TEXT,
    "swift_code": SemanticType.FREE_TEXT,
    "bic": SemanticType.FREE_TEXT,
    "tax_id": SemanticType.FREE_TEXT,
    "vat_number": SemanticType.FREE_TEXT,
    "ticker": SemanticType.FREE_TEXT,
    "symbol": SemanticType.FREE_TEXT,
    "market_cap": SemanticType.MONEY_AMOUNT,
    "volume": SemanticType.NUMERIC_ID,
}


def lookup_lexical(field_name: str) -> SemanticType | None:
    """Look up a field name in the lexical dictionary.
    
    Args:
        field_name: Field name to look up (case-insensitive)
        
    Returns:
        SemanticType if found, None otherwise
    """
    return LEXICAL_DICT.get(field_name.lower())


def get_lexical_entry_count() -> int:
    """Return the number of entries in the lexical dictionary."""
    return len(LEXICAL_DICT)
