# docs/database/auth_schema.md

# Authentication Database Schema

Version: v1

Owner: Track A

Status: Approved

---

# users

Purpose:

Stores platform users.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,

    firebase_uid VARCHAR(255) NOT NULL UNIQUE,

    phone_number VARCHAR(20) NOT NULL UNIQUE,

    name VARCHAR(255),

    role VARCHAR(20) NOT NULL DEFAULT 'USER',

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

# refresh_tokens

Purpose:

Stores active refresh sessions.

Important:

Store hash only.

Never store raw refresh token.

```sql
CREATE TABLE refresh_tokens (

    id UUID PRIMARY KEY,

    user_id UUID NOT NULL,

    token_hash VARCHAR(255) NOT NULL,

    family_id UUID NOT NULL,

    expires_at TIMESTAMP NOT NULL,

    revoked BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    FOREIGN KEY (user_id)
    REFERENCES users(id)
);
```

---

# Recommended Indexes

```sql
CREATE INDEX idx_users_phone
ON users(phone_number);
```

```sql
CREATE INDEX idx_users_firebase_uid
ON users(firebase_uid);
```

```sql
CREATE INDEX idx_refresh_tokens_user
ON refresh_tokens(user_id);
```

```sql
CREATE INDEX idx_refresh_tokens_expiry
ON refresh_tokens(expires_at);
```

```sql
CREATE INDEX idx_refresh_tokens_hash
ON refresh_tokens(token_hash);
```

```sql
CREATE INDEX idx_refresh_tokens_family
ON refresh_tokens(family_id);
```

---

# Constraints

Users

1. Unique phone number
2. Unique Firebase UID

Refresh Tokens

1. Must belong to a valid user
2. Must be hashed
3. Must expire
4. Must support rotation

---

# Refresh Token Rotation

Login

↓

Issue Refresh Token A

↓

Refresh Request

↓

Invalidate Refresh Token A

↓

Issue Refresh Token B

↓

Store Hash(Token B)

↓

Delete or Revoke Token A

This prevents replay attacks.

---

# Refresh Token Family

Each refresh token belongs to a token family.

A family is identified by:

family_id UUID

When a refresh token is rotated:

1. Old token is revoked
2. New token is issued
3. New token inherits the same family_id

If a revoked refresh token is presented:

1. Treat as replay attack
2. Revoke all tokens belonging to that family
3. Force re-authentication

This enables refresh token reuse detection.

---

# Future Tables

Reserved

wallets

transactions

rides

vehicles

docks

notifications

These will be defined in future schema documents.
