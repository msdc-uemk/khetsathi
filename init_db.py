import sqlite3

conn = sqlite3.connect('travel.db')
c = conn.cursor()


c.execute('''
CREATE TABLE IF NOT EXISTS destinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT,
    price REAL,
    description TEXT,
    image_url TEXT
)
''')


c.execute('''
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    destination_id INTEGER,
    travelers INTEGER,
    date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(destination_id) REFERENCES destinations(id)
)
''')


c.execute('DELETE FROM destinations')
sample = [
    ("Goa Beach Getaway", "Goa, India", 120.00, "5 days/4 nights beach package with hotel & breakfast.", "https://picsum.photos/seed/goa/800/500"),
    ("Himalayan Trek", "Manali, India", 250.00, "6 days trekking & homestay experience.", "https://picsum.photos/seed/himalaya/800/500"),
    ("Kerala Backwaters", "Kerala, India", 180.00, "Houseboat stay with local cuisine and sightseeing.", "https://picsum.photos/seed/kerala/800/500"),
]
c.executemany('INSERT INTO destinations (name, location, price, description, image_url) VALUES (?, ?, ?, ?, ?)', sample)

conn.commit()
conn.close()

print("Initialized travel.db with sample destinations.")
