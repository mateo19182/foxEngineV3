from faker import Faker
import csv
import json
import random
from datetime import datetime
import os
from tqdm import tqdm

class DataGenerator:
    def __init__(self):
        self.fake = Faker()
        self.output_dir = "generated_data"
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_user_record(self):
        return {
            "id": self.fake.uuid4(),
            "username": self.fake.user_name(),
            "email": self.fake.email(),
            "name": self.fake.name(),
            "address": self.fake.address(),
            "phone": self.fake.phone_number(),
            "company": self.fake.company(),
            "job_title": self.fake.job(),
            "created_at": self.fake.date_time_this_decade().isoformat(),
            "credit_card": self.fake.credit_card_number(),
            "transaction_amount": round(random.uniform(10, 10000), 2),
            "is_active": random.choice([True, False]),
            "login_count": random.randint(1, 1000),
            "last_login": self.fake.date_time_this_year().isoformat()
        }

    def generate_csv(self, num_records, filename="test_data.csv"):
        filepath = os.path.join(self.output_dir, filename)
        records = []
        
        print(f"\nGenerating {num_records} records for {filename}")
        for _ in tqdm(range(num_records), desc="Generating records"):
            records.append(self.generate_user_record())

        print(f"Writing records to CSV: {filename}")
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            if records:
                writer = csv.DictWriter(csvfile, fieldnames=records[0].keys())
                writer.writeheader()
                for record in tqdm(records, desc="Writing to CSV"):
                    writer.writerow(record)
        
        file_size = os.path.getsize(filepath) / (1024 * 1024)  # Size in MB
        print(f"Generated CSV file: {filepath} ({file_size:.2f} MB)")

    def generate_json(self, num_records, filename="test_data.json"):
        filepath = os.path.join(self.output_dir, filename)
        records = []
        
        print(f"\nGenerating {num_records} records for {filename}")
        for _ in tqdm(range(num_records), desc="Generating records"):
            records.append(self.generate_user_record())
        
        print(f"Writing records to JSON: {filename}")
        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            # Use a generator expression with tqdm to show progress while writing
            json.dump(
                {"users": records},
                jsonfile,
                indent=2
            )
        
        file_size = os.path.getsize(filepath) / (1024 * 1024)  # Size in MB
        print(f"Generated JSON file: {filepath} ({file_size:.2f} MB)")

def main():
    generator = DataGenerator()
    
    # Generate different sized datasets
    sizes = [
        (1000, "small"),
        (10000, "medium"),
        (100000, "large")
    ]
    
    for num_records, size in sizes:
        print(f"\n{'='*50}")
        print(f"Generating {size} dataset ({num_records} records)")
        print(f"{'='*50}")
        
        # Generate CSV
        generator.generate_csv(num_records, f"{size}_dataset.csv")
        
        # Generate JSON
        generator.generate_json(num_records, f"{size}_dataset.json")

if __name__ == "__main__":
    main() 