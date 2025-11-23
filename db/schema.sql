-- Create the database (run this manually if database doesn't exist)
-- CREATE DATABASE groceries;

-- Create stores table
CREATE TABLE IF NOT EXISTS stores (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    location VARCHAR(200),
    website TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create categories table for product categories
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    parent_category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create grocery_deals table
CREATE TABLE IF NOT EXISTS grocery_deals (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    product_name VARCHAR(500) NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    regular_price DECIMAL(10,2),
    sale_price DECIMAL(10,2),
    unit VARCHAR(50), -- e.g., 'lb', 'oz', 'each', 'pack'
    quantity DECIMAL(10,3), -- e.g., 1.5, 2.0
    discount_percentage DECIMAL(5,2), -- e.g., 25.50 for 25.5% off
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    source_url TEXT,
    image_url TEXT,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT valid_date_range CHECK (valid_to >= valid_from)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_stores_name ON stores(name);

CREATE INDEX IF NOT EXISTS idx_categories_name ON categories(name);
CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_category_id);

CREATE INDEX IF NOT EXISTS idx_grocery_deals_uuid ON grocery_deals(uuid);
CREATE INDEX IF NOT EXISTS idx_grocery_deals_store_id ON grocery_deals(store_id);
CREATE INDEX IF NOT EXISTS idx_grocery_deals_category_id ON grocery_deals(category_id);
CREATE INDEX IF NOT EXISTS idx_grocery_deals_product_name ON grocery_deals USING gin(to_tsvector('english', product_name));
CREATE INDEX IF NOT EXISTS idx_grocery_deals_valid_from ON grocery_deals(valid_from);
CREATE INDEX IF NOT EXISTS idx_grocery_deals_valid_to ON grocery_deals(valid_to);
CREATE INDEX IF NOT EXISTS idx_grocery_deals_date_range ON grocery_deals(valid_from, valid_to);
CREATE INDEX IF NOT EXISTS idx_grocery_deals_sale_price ON grocery_deals(sale_price);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers to automatically update updated_at
DROP TRIGGER IF EXISTS update_stores_updated_at ON stores;
CREATE TRIGGER update_stores_updated_at
    BEFORE UPDATE ON stores
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_categories_updated_at ON categories;
CREATE TRIGGER update_categories_updated_at
    BEFORE UPDATE ON categories
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_grocery_deals_updated_at ON grocery_deals;
CREATE TRIGGER update_grocery_deals_updated_at
    BEFORE UPDATE ON grocery_deals
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert sample stores
INSERT INTO stores (name, location, website) VALUES
('Stop and Shop', NULL, 'https://www.stopandshop.com'),
('Hmart', NULL, 'https://www.hmart.com'),
('Stew Leonards', NULL, 'https://www.stewleonards.com'),
('Foodtown', NULL, 'https://www.foodtown.com'),
('Costco', NULL, 'https://www.costco.com'),
('Decicco''s', NULL, NULL)
ON CONFLICT (name) DO NOTHING;

-- Insert sample categories
INSERT INTO categories (name, parent_category_id) VALUES
('Produce', NULL),
('Meat & Seafood', NULL),
('Dairy', NULL),
('Bakery', NULL),
('Frozen', NULL),
('Beverages', NULL),
('Snacks', NULL),
('Pantry', NULL),
('Deli', NULL),
('Organic', NULL)
ON CONFLICT (name) DO NOTHING;

