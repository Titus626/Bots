import random
import time
import pickle
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options


class User:
    def __init__(self):
        self.username = self.create_random_username()
        self.password = self.create_random_password()
        self.email = EmailManager.create_temp_mail(self.username)

    @staticmethod
    def create_random_username():
        return "random_username_{}".format(random.randint(1, 100000))

    @staticmethod
    def create_random_password():
        return "random_password_{}".format(random.randint(1, 100000))


class Registration:
    def __init__(self, driver, user):
        self.driver = driver
        self.user = user

    def register_user(self):
        options = Options()
        options.headless = True
        options.add_argument("--proxy-server=socks5://127.0.0.1:1080")
        self.driver = webdriver.Chrome(options=options)
        self.driver.get('https://tinychat.com/reg')
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, 'username'))).send_keys(self.user.username)
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, 'password'))).send_keys(self.user.password)
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, 'confirm_password'))).send_keys(self.user.password)
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, 'email'))).send_keys(self.user.email)
        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, 'submit'))).click()
        time.sleep(5)
        if 'honeypot' in self.driver.current_url:
            print("Detected honeypot, exiting...")
            self.driver.quit()
            return
        else:
            print(f"Registration successful for {self.user.username}")


class EmailManager:
    @staticmethod
    def create_temp_mail(username):
        domain = "temp-mail.org"
        email = "{}@{}".format(username, domain)
        return email

    @staticmethod
    def save_email(email):
        with open('email_addresses.pkl', 'wb') as f:
            pickle.dump(email, f)


def main():
    driver = webdriver.Chrome(options=options)
    users = [User() for _ in range(15)]

    for user in users:
        Registration(driver, user).register_user()
        EmailManager.save_email(user.email)

    time.sleep(5)
    driver.quit()


if __name__ == '__main__':
    main()
