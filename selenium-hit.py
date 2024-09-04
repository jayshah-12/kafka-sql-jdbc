import os
import pandas as pd
from sqlalchemy import create_engine, Integer
from sqlalchemy.types import Integer as SQLInteger
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Fetch username and password from environment variables
username = os.getenv('SCRAPER_USERNAME', 'jayshah36262@gmail.com')
password = os.getenv('SCRAPER_PASSWORD', 'Jayshah12')

# Define MySQL connection parameters
mysql_user = os.getenv('MYSQL_USER', 'root')
mysql_password = os.getenv('MYSQL_PASSWORD', 'root')
mysql_host = os.getenv('MYSQL_HOST', '192.168.3.112')
mysql_database = os.getenv('MYSQL_DATABASE', 'my_db')

# Create SQLAlchemy engine for MySQL
engine = create_engine(f'mysql+mysqlconnector://{mysql_user}:{mysql_password}@{mysql_host}/{mysql_database}')

# Read the CSV file containing company names and symbols
companies_df = pd.read_csv('company.csv')  # Assuming the CSV file is named 'company.csv'
print(companies_df.columns)

# Setup Chrome options for headless mode
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Path to the ChromeDriver you installed
driver = webdriver.Chrome(options=chrome_options)

# Login URL and page
login_url = "https://www.screener.in/login/?"
driver.get(login_url)

# Find and fill the login form
try:
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'csrfmiddlewaretoken')))
    csrf_token = driver.find_element(By.NAME, 'csrfmiddlewaretoken').get_attribute('value')

    username_input = driver.find_element(By.NAME, 'username')
    password_input = driver.find_element(By.NAME, 'password')
    csrf_token_input = driver.find_element(By.NAME, 'csrfmiddlewaretoken')
    
    username_input.send_keys(username)
    password_input.send_keys(password)
    csrf_token_input.send_keys(csrf_token)

    login_button = driver.find_element(By.XPATH, '//button[@type="submit"]')
    login_button.click()
    
    # Wait for login to complete
    WebDriverWait(driver, 10).until(EC.url_changes(login_url))
    if driver.current_url == "https://www.screener.in/dash/":
        print("Login successful.")
    else:
        print("Login failed.")
        driver.quit()
        exit()

except Exception as e:
    print(f"Error during login: {e}")
    driver.quit()
    exit()

# Initialize DataFrames to store combined data
combined_data = pd.DataFrame()
combined_ttm = pd.DataFrame()

for _, row in companies_df.iterrows():
    company_name = row['Company_Name']
    symbol = row['Symbol']
    search_url = f"https://www.screener.in/company/{symbol}/consolidated/"
    driver.get(search_url)
    
    try:
        # Wait for the page to load and the table to be present
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'profit-loss')))
        table = driver.find_element(By.ID, 'profit-loss').find_element(By.TAG_NAME, 'table')

        headers = [th.text.strip() or f'Column_{i}' for i, th in enumerate(table.find_elements(By.TAG_NAME, 'th'))]
        rows = table.find_elements(By.TAG_NAME, 'tr')

        row_data = []
        for row in rows[1:]:
            cols = row.find_elements(By.TAG_NAME, 'td')
            cols = [col.text.strip() for col in cols]
            if len(cols) == len(headers):
                row_data.append(cols)
            else:
                print(f"Row data length mismatch for symbol {symbol}: {cols}")

        # Create a DataFrame with sanitized headers
        df = pd.DataFrame(row_data, columns=headers)

        if not df.empty:
            df.columns = ['Narration'] + df.columns[1:].tolist()
            df = df.reset_index(drop=True)

            try:
                # Attempt to drop 'TTM' column and process DataFrame
                temp = df.drop(columns=['TTM'])
                data = pd.melt(temp, id_vars=['Narration'], var_name='Year', value_name='Value')
                data = data.sort_values(by=['Narration', 'Year']).reset_index(drop=True)
                data['Value'] = data['Value'].str.replace(',', '').str.replace('%', '').astype(float)
                data['ttm_id'] = None
                data['Company_Name'] = company_name

                # Process the 'ttm' DataFrame
                ttm = df[['Narration', 'TTM']]
                ttm['TTM'] = ttm['TTM'].str.replace(',', '').str.replace('%', '')
                ttm.insert(0, 'id2', range(1, len(ttm) + 1))
                ttm['Company_Name'] = company_name
                narration_to_id = ttm.set_index('Narration')['id2'].to_dict()
                data['ttm_id'] = data['Narration'].map(narration_to_id)

                ttm = ttm.drop(columns=['id2'])
                combined_data = pd.concat([combined_data, data], ignore_index=True)
                combined_ttm = pd.concat([combined_ttm, ttm], ignore_index=True)

            except KeyError as e:
                print(f"Column 'TTM' not found in DataFrame for symbol {symbol}: {e}")
                continue

            except Exception as e:
                print(f"Error processing data for symbol {symbol}: {e}")
                continue
        else:
            print(f"Failed to find the data table for symbol: {symbol}.")
        
    except Exception as e:
        print(f"Error retrieving data for symbol {symbol}: {e}")
    
    time.sleep(3)

# Combine all DataFrames
desired_order_ttm = ['Company_Name', 'Narration', 'TTM']
combined_ttm = combined_ttm[desired_order_ttm]

# Save combined DataFrames to SQL
combined_data.to_sql('data', con=engine, if_exists='append', index=True, index_label='id', dtype={'id': SQLInteger()})
combined_ttm.to_sql('ttm', con=engine, if_exists='append', index=True, index_label='id')
print("All data successfully loaded into MySQL.")

# Close the browser
driver.quit()
