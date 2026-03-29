# MKMagnolia 🌸

A Django web application to track and log magnolia sightings in Milton Keynes.

## Features

- Log magnolia sightings with species, location, date and blooming status
- Attach photos to sightings
- Record GPS coordinates with a link to OpenStreetMap
- Browse and search all sightings
- Edit and delete existing entries

## Setup

### Prerequisites

- Python 3.10+

### Installation

```bash
# Clone the repository
git clone https://github.com/matbest/MKMagnolia.git
cd MKMagnolia

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Apply database migrations
python manage.py migrate

# (Optional) Create an admin user
python manage.py createsuperuser

# Start the development server
python manage.py runserver
```

The site will be available at http://127.0.0.1:8000/.

## Running Tests

```bash
python manage.py test magnolias
```

## Admin Interface

Visit http://127.0.0.1:8000/admin/ to manage sightings via the Django admin interface.
