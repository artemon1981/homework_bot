"""Бот для проверки заданий Практикума."""
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TIME_TO_REWIEW = 604800
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID}
    token_missing = True
    for name, token in tokens.items():
        if not token:
            logging.critical(f'Отсутствуют обязательные '
                             f'переменные окружения: {name}')
            token_missing = False
    return token_missing


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.debug(f'Бот отправил сообщение: "{message}"')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        logging.error(f'Боту не удалось отправить сообщение: "{error}"')


def get_api_answer(timestamp):
    """Делает запрос к  эндпоинту API-сервиса."""
    timestamp = timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        message = f'Эндпоинт {ENDPOINT} недоступен: {error}'
        logging.error(message)
        raise exceptions.GetAPIAnswerException(message)
    if homework_statuses.status_code != HTTPStatus.OK:
        message = f'Код ответа API: {homework_statuses.status_code}'
        logging.error(message)
        raise exceptions.GetAPIAnswerException(message)
    return homework_statuses.json()


def check_response(response):
    """Проверяет корректность данных."""
    if not isinstance(response, dict):
        message = (f'Тип данных в ответе  не соотвествует ожидаемому.'
                   f' Получен: {type(response)}')
        logging.error(message)
        raise TypeError(message)
    if 'homeworks' not in response:
        message = 'Ключ homeworks недоступен'
        logging.error(message)
        raise exceptions.CheckResponseException(message)
    homeworks_list = response['homeworks']
    if not isinstance(homeworks_list, list):
        message = ('В ответе домашки приходят не в виде списка. '
                   f'Получен: {type(homeworks_list)}')
        logging.error(message)
        raise TypeError(message)
    return homeworks_list


def parse_status(homework):
    """Извлекает из информации о конкретной домашке её статус."""
    keys_name_status = ['homework_name', 'status']
    for key in keys_name_status:
        if key not in homework:
            message = f'Ключ {key} недоступен'
            logging.error(message)
            raise KeyError(message)

    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
        return (f'Изменился статус проверки работы '
                f'"{homework_name}". {verdict}')

    message = (f'Передан неизвестный статус '
               f'домашней работы "{homework_status}"')
    logging.error(message)
    raise exceptions.ParseStatusException(message)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise SystemExit('Не хватает обязательных переменных окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - TIME_TO_REWIEW
    current_status = ''
    current_error = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logging.info('Статус не обновлен')
            for homework in homeworks:
                homework_status = parse_status(homework)
                if current_status == homework_status:
                    logging.info(homework_status)
                else:
                    current_status = homework_status
                    send_message(bot, homework_status)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if current_error != error:
                current_error = error
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s, '
                               '%(levelname)s, '
                               '%(message)s, '
                               '%(name)s',
                        stream=sys.stdout)
    main()
