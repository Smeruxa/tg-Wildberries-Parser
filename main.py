TOKEN = ""

import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

def get_soup(query):
    driver = webdriver.Chrome(service=Service('driver/chromedriver.exe'), options=chrome_options)
    driver.get(f"https://www.wildberries.ru/catalog/0/search.aspx?search={query}")
    WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CLASS_NAME, 'product-card-list')))
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()
    return soup

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    await message.answer("Введите название товара, чтобы получить список продуктов.")

@dp.message()
async def handle_search(message: types.Message, state: FSMContext):
    await state.update_data(products=[], current_index=0)

    query = message.text
    await message.reply("Ищу товар, пожалуйста подождите...")

    try:
        products_info = await search_product(query)
        if products_info:
            await state.update_data(products=products_info)
            await show_product(message, state)
        else:
            await message.reply("Товары не найдены.")
    except Exception as e:
        await message.reply(f"Произошла ошибка при поиске товара: {e}")

async def search_product(query):
    soup = await asyncio.to_thread(get_soup, query)
    product_cards = soup.find_all('article', {'class': 'product-card'})
    
    products_info = [
        {
            "name": card.find('span', {'class': 'product-card__name'}).text.strip(),
            "price": card.find('ins', {'class': 'price__lower-price'}).text.strip(),
            "url": card.find('a', {'class': 'product-card__link'})['href'],
            "image": card.find('img', {'class': 'j-thumbnail'})['src'] if card.find('img', {'class': 'j-thumbnail'}) else None
        }
        for card in product_cards if card.find('span', {'class': 'product-card__name'}) and card.find('ins', {'class': 'price__lower-price'})
    ]
    
    return products_info

async def show_product(message_or_callback, state: FSMContext, callback_query: types.CallbackQuery = None):
    user_data = await state.get_data()
    products_info = user_data.get('products', [])
    current_index = user_data.get('current_index', 0)

    if products_info:
        selected_product = products_info[current_index]
        text = (f"Номер товара: {current_index + 1} из {len(products_info)}\n"
                f"Название: {escape_markdown(selected_product['name'])}\n"
                f"Цена: {escape_markdown(selected_product['price'])}\n")

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Влево", callback_data='left'),
                InlineKeyboardButton(text="Вправо ➡️", callback_data='right')
            ],
            [InlineKeyboardButton(text="Перейти к товару", url=selected_product['url'])],
            [InlineKeyboardButton(text="Сбросить", callback_data='reset')]
        ])

        if callback_query:
            if selected_product['image']:
                media = InputMediaPhoto(media=selected_product['image'], caption=text, parse_mode=ParseMode.MARKDOWN_V2)
                await bot.edit_message_media(media=media, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, reply_markup=keyboard)
            else:
                await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            if selected_product['image']:
                await message_or_callback.answer_photo(photo=selected_product['image'], caption=text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await message_or_callback.answer(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await message_or_callback.answer("Нет доступных товаров для показа.")

@dp.callback_query(lambda c: c.data in ['left', 'right'])
async def navigate_products(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_index = user_data.get('current_index', 0)
    products_info = user_data.get('products', [])

    if callback_query.data == 'left':
        current_index = (current_index - 1) % len(products_info)
    elif callback_query.data == 'right':
        current_index = (current_index + 1) % len(products_info)

    await state.update_data(current_index=current_index)
    await show_product(callback_query.message, state, callback_query)

@dp.callback_query(lambda c: c.data == 'reset')
async def reset_search(callback_query: types.CallbackQuery, state: FSMContext):
    await state.update_data(products=[], current_index=0)
    await callback_query.message.delete()
    await callback_query.message.answer("Введите название товара, чтобы получить список продуктов.")
    await callback_query.answer()

def escape_markdown(text: str) -> str:
    return ''.join(f'\\{char}' if char in r'\_*[]()~`>#+-=|{}.!' else char for char in text)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
