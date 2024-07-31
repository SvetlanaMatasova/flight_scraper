import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
import logging
import os
import time


# Определите абсолютные пути к файлам
base_dir = r'C:\Users\Светлана\PycharmProjects\parser'
log_file_path = os.path.join(base_dir, 'script_log.txt')
data_file_path = os.path.join(base_dir, 'flight_prices.txt')

# Настройка логирования
logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def send_telegram_message(message):
    token = '6602655270:AAH49A8yiZ9et7StBeLP1gkjvXgDmRjkpiw'

    chat_ids = ['1480863151', '6416922017']
    # chat_id = '1480863151'
    url = f'https://api.telegram.org/bot{token}/sendMessage'

    for chat_id in chat_ids:
        payload = {
            'chat_id': chat_id,
            'text': message
        }
        try:
            response = requests.post(url, data=payload)
            response.raise_for_status()
            print(f'Telegram message sent successfully to chat_id {chat_id}')
        except requests.exceptions.RequestException as e:
            print(f'Error sending Telegram message to chat_id {chat_id}: {e}')
            logging.error(f'Error sending Telegram message to chat_id {chat_id}: {e}')


def write_to_file(filename, data):
    try:
        with open(filename, 'a', encoding='utf-8') as file:
            file.write(data)
    except IOError as e:
        logging.error(f'File write error: {e}')

# Старая версия сайта
def collect_flight_data_old(driver):
    flight_data = []
    time.sleep(4)
    # Собираем данные о рейсах
    flights = driver.find_elements(By.CSS_SELECTOR, "span[data-v-tippy] div.flight-date-selector__item")
    for flight in flights:
        date_element = flight.find_element(By.CSS_SELECTOR, "div.flight-date-selector__date")
        price_element = flight.find_element(By.CSS_SELECTOR, "div.flight-date-selector__price")
        date = date_element.text
        price = price_element.text
        flight_data.append((date, price))
    return flight_data

def scrape_flight_data_old(driver):
    wait = WebDriverWait(driver, 10)
    all_flight_data = []

    # Собираем данные и обновляем их 8 раз
    for _ in range(8):
        # Собираем данные о текущих рейсах
        flight_data = collect_flight_data_old(driver)
        all_flight_data.extend(flight_data)

        # Нажимаем кнопку слайдера для загрузки новых данных
        slider_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.flight-date-selector__next")))
        slider_button.click()

        # Ждем, пока страница полностью загрузится после обновления
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span[data-v-tippy] div.flight-date-selector__item")))

    return all_flight_data

# Новая версия сайта
def collect_flight_data_new(driver):
    flight_data = []
    try:
        time.sleep(3)  # Дождитесь, пока элементы загрузятся

        # Ожидаем видимости элементов с датами
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.matrix-date-selector"))
        )

        # Получаем элементы с датами
        date_elements = driver.find_elements(By.CSS_SELECTOR, "div.matrix-date-selector__date")

        # Получаем элементы с ценами
        price_elements = driver.find_elements(By.CSS_SELECTOR, "div.search-matrix__table-row > div.search-matrix__table-cell")

        dates = [elem.text.strip() for elem in date_elements]

        # Обработка цен
        prices = []
        for elem in price_elements:
            if '<!---->' in elem.get_attribute('outerHTML'):
                prices.append('0')
            else:
                price_content = elem.find_element(By.CSS_SELECTOR, "span.tsh-price__content")
                if price_content:
                    price_text = price_content.text.strip().replace('\xa0', '').replace('₽', '')
                    prices.append(price_text)
                else:
                    prices.append('0')

        # Проверяем, что количество дат и цен совпадает
        if len(dates) != len(prices):
            logging.warning(f'Количество дат ({len(dates)}) не совпадает с количеством цен ({len(prices)})')

        # Заполняем недостающие цены нулями
        if len(prices) < len(dates):
            prices += ['0'] * (len(dates) - len(prices))

        for date, price in zip(dates, prices):
            flight_data.append((date, price))

    except Exception as e:
        logging.error(f'Error collecting flight data: {e}')

    return flight_data

def click_next_button(driver):
    try:
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.matrix-date-selector__next"))
        )
        next_button.click()
        time.sleep(3)  # Дождитесь, пока загрузится следующая страница
    except Exception as e:
        logging.error(f'Error clicking next button: {e}')

def scrape_flight_data_new(driver):
    all_flight_data = []

    for i in range(6):  # Перелистываем страницы 6 раз
        logging.info(f'Scraping page {i + 1}')
        flight_data = collect_flight_data_new(driver)
        all_flight_data.extend(flight_data)

        # Нажимаем на кнопку для перехода к следующей странице
        click_next_button(driver)

    return all_flight_data

# Основная функция для запуска скрипта
def scrape_flight_data(url):
    # Инициализация драйвера
    service = ChromeService(executable_path=ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    driver.get(url)

    # Ожидаем 8 секунд для полной загрузки страницы
    WebDriverWait(driver, 8).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
    )
    time.sleep(5)
    # Проверяем наличие элемента для определения версии сайта
    try:
        if driver.find_elements(By.CSS_SELECTOR, "div.flight-date-selector__date"):
            logging.info('Old version detected')
            all_flight_data = scrape_flight_data_old(driver)
        elif driver.find_elements(By.CSS_SELECTOR, "div.matrix-date-selector__date"):
            logging.info('New version detected')
            all_flight_data = scrape_flight_data_new(driver)
        else:
            logging.error('Не удалось определить версию сайта')
            all_flight_data = []
    except Exception as e:
        logging.error(f'Ошибка при определении версии сайта: {e}')
        all_flight_data = []

    # Закрываем браузер
    driver.quit()

    return all_flight_data



try:
    logging.info('Started script')

    # URL страницы с результатами поиска
    current_date = datetime.now().strftime("%d.%m.%Y")

    # Формируем URL с текущей датой
    url_template = 'https://booking.azimuth.ru/new/#/!/TLV/AER/{}/1-1-0/'
    url = url_template.format(current_date)
    # url = 'https://booking.azimuth.ru/new/#/!/TLV/AER/28.07.2024/1-1-0/'
    flight_data = scrape_flight_data(url)

    # Вывод всех считанных данных в консоль
    print("Данные до сортировки:")
    filtered_flight_data = [data for data in flight_data if data[1] != '0']
    for data in filtered_flight_data:
        print(f"{data[0]} - {data[1]}")

    # Найти три минимальные цены
    sorted_flights = sorted(filtered_flight_data, key=lambda x: float(x[1].replace(' ', '') or '0'), reverse=False)
    lowest_prices = sorted_flights[:6]

    # Получить текущее время и дату
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Подготовить данные для записи
    data_to_write = f"{current_time} |||"

    for flight in lowest_prices:
        data_to_write += f" {flight[0]} - {flight[1]} |"
    data_to_write += "\n"

    # Записать данные в файл
    write_to_file(data_file_path, data_to_write)

    print("Данные после сортировки:")
    for data in lowest_prices:
        print(f"{data[0]} - {data[1]}")

    if filtered_flight_data:
        min_price = min(float(flight[1].replace(' ', '')) for flight in filtered_flight_data)

        # Найти все рейсы с минимальной ценой
        lowest_price_flights = [flight for flight in filtered_flight_data if
                                float(flight[1].replace(' ', '')) == min_price]

        # Формируем сообщение для отправки
        if lowest_prices and float(lowest_prices[0][1].replace(' ', '')) < 25000:
            message = "Рейсы с самой низкой ценой Тель-Авив - Сочи:\n"
            for flight in lowest_price_flights:
                message += f"{flight[0]} - {flight[1]}\n"
            print(message)
            send_telegram_message(message)

    logging.info('Finished script')

except Exception as e:
    logging.error(f'Error: {e}')


# https://github.com/SvetlanaMatasova/flight_scraper.git


# import os
# import logging
# import shutil
# from webdriver_manager.chrome import ChromeDriverManager
#
# # Настройка логирования
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
#
#
# def clear_chromedriver_cache():
#     # Определите путь к кэшу chromedriver
#     cache_dir = os.path.expanduser("~/.wdm/drivers")
#
#     # Удалите кэш, если он существует
#     if os.path.exists(cache_dir):
#         try:
#             shutil.rmtree(cache_dir)
#             logging.info('Cleared WebDriver manager cache')
#         except Exception as e:
#             logging.error(f'Error clearing cache: {e}')
#     else:
#         logging.info('No cache directory found')
#
#
# def install_chromedriver():
#     try:
#         # Установите последнюю версию chromedriver
#         driver_path = ChromeDriverManager().install()
#         logging.info(f'Installed chromedriver at {driver_path}')
#     except Exception as e:
#         logging.error(f'Error installing chromedriver: {e}')
#
#
# if __name__ == "__main__":
#     logging.info('Starting script')
#     clear_chromedriver_cache()
#     install_chromedriver()
#     logging.info('Finished script')
