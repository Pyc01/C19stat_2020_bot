import telegram
import logging
import os
import io
import pandas as pd
import plotly.express as px
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, InlineQueryHandler, CallbackQueryHandler, ConversationHandler
from telegram import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
from io import BytesIO
from PIL import Image

TOKEN = 'YOUR_TOKEN_HERE'
# username = c19stat_2020_bot, name = C19 Stat
PORT = int(os.environ.get('PORT', 5000))
NUM_COUNTRIES_IN_SET = 10

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def custom_keyboard():
    keyboard = [['\U0001F4DD' + 'C19 Top 10', '\U0001F4CA' + 'Графики']]
    reply_markup = telegram.ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    return reply_markup


def start(update, context):
    user = update.message.from_user
    logger.info("User %s started the conversation.", user.first_name)
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Телеграм-бот выводит статистику и графики по ситуации COVID-19 в мире. \n"
                                  "Данные берутся из репозитория университета Джонса Хопкинса. \n"
                                  "Для обработки данных может потребоваться до 10 секунд на ответ, сохраняйте спокойствие. \n"
                                  "Для инициализации бота можно использовать стандартную комманду: /start",
                             reply_markup=custom_keyboard())


def echo(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)


def unknown(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Неправильная комманда")


def get_dataframe():
    dataf = pd.read_csv(
        'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv', sep=',', encoding='utf8')
    return dataf


def chart(countr):
    country_one_alt = g_df.loc[g_df['Country/Region'] == countr].T.squeeze()  # берем строку только с выбранной страной

    differenceframe = country_one_alt.iloc[4:len(country_one_alt.index), ].diff()  # дневные приросты выбранной страны (альтернативный метод)
    differenceframe = differenceframe.reset_index()
    differenceframe.rename(columns={differenceframe.columns[-1]: 'Cases'}, inplace=True)

    fig = px.bar(differenceframe, x="index", y="Cases", title=countr)  # рисуем график
    fig.update_traces(marker_color='orange')  # меняем цвет баров
    img_bytes = fig.to_image(format="png", engine="kaleido")

    im = Image.open(io.BytesIO(img_bytes))

    bio = BytesIO()
    bio.name = 'image.png'
    im.save(bio, 'PNG')
    bio.seek(0)

    return bio



def stat_start(update, context):
    update.message.reply_text("Готовлю статистику.\nОбратите внимание - будут показаны данные "
                              "по вчерашний день (так как сегодняшний день еще на закончился и статистика не собрана). ", reply_markup=custom_keyboard())
    df = get_dataframe()  # получаем свежий датафрейм

    last_column_date = list(df.columns)[-1]  # получаем актуальную дату (самую последнюю доступную)

    top_countr = df.iloc[:, [1, len(df.columns) - 1]].nlargest(NUM_COUNTRIES_IN_SET, [list(df.columns)[-1]], keep='all')  # только NUM_COUNTRIES_IN_SET максимальных по последней колонке

    alldata_sorted = df.nlargest(NUM_COUNTRIES_IN_SET, [list(df.columns)[-1]], keep='all')  # NUM_COUNTRIES_IN_SET максимальных по последней колонке все данные

    day_increment = alldata_sorted.iloc[:, 4:len(df.columns)].diff(axis=1).iloc[:, [-1]]  # вычисляем дневной прирост по последним двум дням
    day_increment.rename(columns={day_increment.columns[-1]: 'Daily'}, inplace=True)  # Переименовываем колонку с датой в Daily

    result01 = pd.concat([top_countr, day_increment], axis=1).reindex(top_countr.index)  # объединенный результат
    result01.rename(columns={result01.columns[0]: 'Country'}, inplace=True)  # Переименовываем колонку Country/Region в Country
    result01.replace('South Africa', 'SAfrica', inplace=True)  # Переименовываем South Africa в SAfrica, а то таблицу рвет
    result01['Daily'] = result01['Daily'].map('{:,.0f}'.format)  # Форматируем представление данных
    result01[list(df.columns)[-1]] = result01[list(df.columns)[-1]].map('{:,.0f}'.format)  # Форматируем представление данных
    result01 = result01.to_string(columns=['Country', last_column_date, 'Daily'], index=False, header=True)  # формируем данные для бота

    update.message.reply_text("Статистика по Top10 странам:", reply_markup=custom_keyboard())
    update.message.reply_html('<pre>' + result01 + '</pre>', parse_mode='HTML', reply_markup=custom_keyboard())  # Выводим статистику


def graph_start(update, context):
    update.message.reply_text('Подготавливаю список стран, ожидайте')  # вопрос и убираем основную клавиатуру , reply_markup=ReplyKeyboardRemove()

    global g_df
    g_df = get_dataframe()  # получаем свежий датафрейм, делаем его глобальным

    top_countr = g_df.iloc[:, [1, len(g_df.columns) - 1]].nlargest(NUM_COUNTRIES_IN_SET, [list(g_df.columns)[-1]], keep='all')  # только NUM_COUNTRIES_IN_SET максимальных по последней колонке

    list_of_top10_countries = top_countr.iloc[:, 0].tolist()  # передаем топ 10 стран из датафрейма в список

    global regex_string
    regex_string = list_of_top10_countries[0] + '|' + \
                   list_of_top10_countries[1] + '|' + \
                   list_of_top10_countries[2] + '|' + \
                   list_of_top10_countries[3] + '|' + \
                   list_of_top10_countries[4] + '|' + \
                   list_of_top10_countries[5] + '|' + \
                   list_of_top10_countries[6] + '|' + \
                   list_of_top10_countries[7] + '|' + \
                   list_of_top10_countries[8] + '|' + \
                   list_of_top10_countries[9]

    reply_keyboard = [[list_of_top10_countries[0], list_of_top10_countries[1], list_of_top10_countries[2]],
                      [list_of_top10_countries[3], list_of_top10_countries[4], list_of_top10_countries[5]],
                      [list_of_top10_countries[6], list_of_top10_countries[7], list_of_top10_countries[8]],
                      [list_of_top10_countries[9], "Назад"]]
    update.message.reply_text("Для какой страны из Top10 составить график?", reply_markup=telegram.ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True))  # , one_time_keyboard=True

    return "country_choise"  # ключ для определения следующего шага


def chose_country(update, context):
    context.user_data['country_choise'] = update.message.text

    selected_country = update.message.text

    if selected_country in regex_string:
        update.message.reply_text("Готовлю график для "+selected_country+", ожидайте", reply_markup=custom_keyboard())

        bio = chart(selected_country)

        update.message.reply_photo(photo=bio, reply_markup=custom_keyboard())

    elif selected_country == 'Назад':
        update.message.reply_text("Выберите Статистику или Графики", reply_markup=custom_keyboard())

    else:
        update.message.reply_text("Такой страны нет в списке", reply_markup=custom_keyboard())  # обработка, если юзер будучи внутри конверсейшена напечатал что-то на клавиатуре вместо выбора по кнопке

    return ConversationHandler.END


def main():
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('start', start))
    
    regex_string = ''

    dispatcher.add_handler(ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('\U0001F4CA' + 'Графики'), graph_start)],
        states={
            "country_choise": [MessageHandler(Filters.regex(regex_string), chose_country)],
        },
        fallbacks=[MessageHandler(Filters.text | Filters.video | Filters.photo | Filters.document, unknown)]
    )
    )

    dispatcher.add_handler(MessageHandler(Filters.regex('\U0001F4DD' + 'C19 Top 10'), stat_start))
    dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), echo))
    dispatcher.add_handler(MessageHandler(Filters.command, unknown))

    # updater.start_polling()
    updater.start_webhook(listen="0.0.0.0", port=int(PORT), url_path=TOKEN)
    updater.bot.setWebhook('https://floating-plains-56473.herokuapp.com/' + TOKEN)

    updater.idle()


if __name__ == '__main__':
    main()
