from faker import Faker
import csv
import json
import random
import os
import time
from tqdm import tqdm
import multiprocessing as mp
from datetime import datetime

def worker_init():
    """
    Resets the random generator so that each process gets a unique seed.
    """
    seed = os.getpid() + int(time.time() * 1000)
    random.seed(seed)

class DataGenerator:
    def __init__(self, multivalue_separator=","):
        self.output_dir = "data/"
        self.multivalue_separator = multivalue_separator
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_user_record(self, record_id):
        """
        Generate a single user record with varied values.
        A local Faker instance is created and seeded with a combination
        of the process ID and the record's unique integer to boost uniqueness.
        """
        fake_local = Faker()
        fake_local.seed_instance(os.getpid() + record_id)
        
        # Append record_id to the username to ensure uniqueness.
        username = f"{fake_local.user_name()}_{record_id}"

        # Generate multi-valued emails (1–3 emails)
        num_emails = random.randint(1, 3)
        emails = [fake_local.email() for _ in range(num_emails)]

        # Generate a single full name
        name = fake_local.name()

        # Generate multi-valued addresses (1–2 addresses) and remove newlines.
        num_addresses = random.randint(1, 2)
        addresses = [fake_local.address().replace("\n", " ") for _ in range(num_addresses)]
        
        # Generate multi-valued phone numbers (1–2 phone numbers)
        num_phones = random.randint(1, 2)
        phones = [fake_local.phone_number() for _ in range(num_phones)]
        
        company = fake_local.company()
        job = fake_local.job()
        credit_card = fake_local.credit_card_number()

        transaction_amount = round(random.uniform(100, 10000), 2)
        is_active = random.choice([True, False])
        login_count = random.randint(1, 1000)

        return {
            "username": username,
            "email": emails,       # multi-valued
            "name": name,
            "address": addresses,  # multi-valued
            "phone": phones,       # multi-valued
            "company": company,
            "job_title": job,
            "credit_card": credit_card,
            "transaction_amount": transaction_amount,
            "is_active": is_active,
            "login_count": login_count
        }

    def format_record(self, record):
        """
        Format a record so that:
          - Multi-valued fields (email, address, phone) are joined using the specified multivalue separator
            and wrapped in double quotes.
          - Single-valued string fields are cleaned to remove commas (and extra quotes) so they don't
            interfere with the CSV delimiter.
        """
        multivalued_fields = ["email", "address", "phone"]
        formatted_record = {}
        for key, value in record.items():
            if key in multivalued_fields and isinstance(value, list):
                # Clean each item (remove commas and quotes) before joining.
                cleaned_items = [item.replace(",", " ").replace('"', '') for item in value]
                formatted_record[key] = f'"{self.multivalue_separator.join(cleaned_items)}"'
            elif isinstance(value, str):
                # Remove commas and quotes from single-value strings.
                formatted_record[key] = value.replace(",", " ").replace('"', '')
            else:
                formatted_record[key] = value
        return formatted_record

    def generate_records_parallel(self, num_records):
        """
        Use all available CPU cores to generate records in parallel.
        Each record's unique integer is passed so that we can guarantee variation.
        """
        num_cores = mp.cpu_count()
        with mp.Pool(num_cores, initializer=worker_init) as pool:
            records = list(
                tqdm(
                    pool.imap(self.generate_user_record, range(num_records)),
                    total=num_records,
                    desc="Generating records"
                )
            )
        return records

    def generate_csv(self, num_records, filename="test_data.csv"):
        filepath = os.path.join(self.output_dir, filename)
        print(f"\nGenerating {num_records} records for CSV file: {filename}")
        records = self.generate_records_parallel(num_records)

        # Enforce uniqueness based on (username, primary email).
        seen_records = set()
        unique_records = []
        for record in records:
            key = (record['username'], record['email'][0])
            if key not in seen_records:
                seen_records.add(key)
                unique_records.append(record)

        print(f"Writing {len(unique_records)} unique records to CSV: {filename}")
        formatted_records = [self.format_record(rec) for rec in unique_records]

        # The ingestion service expects these column names.
        fieldnames = [
            "username", "email", "name", "address", "phone",
            "company", "job_title", "credit_card",
            "transaction_amount", "is_active", "login_count"
        ]

        # Write CSV using a comma as the column delimiter.
        # QUOTE_NONE is used as we have already cleaned and formatted fields.
        # We now include escapechar to avoid the _csv.Error when a field requires escaping.
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(
                csvfile,
                fieldnames=fieldnames,
                delimiter=',',
                quoting=csv.QUOTE_NONE,
                escapechar='\\'
            )
            writer.writeheader()
            writer.writerows(formatted_records)

        file_size = os.path.getsize(filepath) / (1024 * 1024)  # Size in MB
        print(f"Generated CSV file: {filepath} ({file_size:.2f} MB)")

    def generate_json(self, num_records, filename="test_data.json"):
        filepath = os.path.join(self.output_dir, filename)
        print(f"\nGenerating {num_records} records for JSON file: {filename}")
        records = self.generate_records_parallel(num_records)

        # Enforce uniqueness based on (username, primary email).
        seen_records = set()
        unique_records = []
        for record in records:
            key = (record['username'], record['email'][0])
            if key not in seen_records:
                seen_records.add(key)
                unique_records.append(record)

        print(f"Writing {len(unique_records)} unique records to JSON: {filename}")
        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump({"rows": unique_records}, jsonfile, indent=None)

        file_size = os.path.getsize(filepath) / (1024 * 1024)  # Size in MB
        print(f"Generated JSON file: {filepath} ({file_size:.2f} MB)")

def main():
    # Allow specifying multivalue separator as an environment variable
    multivalue_separator = os.environ.get("MULTIVALUE_SEPARATOR", ",")
    generator = DataGenerator(multivalue_separator=multivalue_separator)

    # Generate datasets of various sizes.
    sizes = [
        (1000, "S"),
        (10000, "M"),
        (100000, "L"),
        (1000000, "XL")
    ]

    for num_records, size in sizes:
        print("\n" + "="*50)
        print(f"Generating {size} dataset ({num_records} records)")
        print("="*50)

        generator.generate_csv(num_records, f"{size}_dataset.csv")
        generator.generate_json(num_records, f"{size}_dataset.json")

if __name__ == "__main__":
    main()