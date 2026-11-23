# ERD TokoKita

```mermaid
erDiagram
    USERS ||--o{ SALES : mencatat
    PRODUCTS ||--o{ SALES : terjual
    CUSTOMERS ||--o{ SALES : membeli

    USERS {
        bigint id PK
        varchar username
        text password_hash
        timestamp created_at
    }
    PRODUCTS {
        bigint id PK
        varchar sku
        varchar name
        bigint price
        bigint stock
    }
    CUSTOMERS {
        bigint id PK
        varchar name
        varchar phone
        varchar email
    }
    SALES {
        bigint id PK
        bigint customer_id FK
        bigint product_id FK
        bigint user_id FK
        bigint quantity
        bigint unit_price
        bigint total
        timestamp created_at
    }
```

- **Master**: `products`, `customers`.
- **Transaksi**: `sales`.
- **Login/Register**: `users`.
- **Report**: hasil query JOIN tabel `sales`, `products`, `customers`; tidak membutuhkan tabel baru.
