import os
import warnings
import requests
import json
import pandas as pd

from pandas import DataFrame
from flask import Flask, request, abort

from linebot import LineBotSdkDeprecatedIn30

from linebot import (
    LineBotApi
)
from linebot.v3.messaging import (
    Configuration
)
from linebot.v3.webhook import (
    WebhookHandler
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    TextMessage, TemplateSendMessage, CarouselTemplate, CarouselColumn)

app = Flask(__name__)

access_token='cl2ehA91yxD/3uJRzDyls9SlRQTcprQVs7wRkMxog6d8LQK1+L9Z4SWnQoUukY5C8JNjml7xLrON9D7RMDfDeKyov5+tQ7WuSsA/5kTAB+5BgR/+7t9FIGzr/IqWu9Z9Guv9vzP526VC43HDjtOdWAdB04t89/1O/w1cDnyilFU='

line_bot_api = LineBotApi(access_token)
handler = WebhookHandler('3879d5592c6cff489b2ce1540972e4de')
res_rakuten = requests.get('https://app.rakuten.co.jp/services/api/Recipe/CategoryList/20170426?applicationId=1043289948570835263')
rakuten_data = json.loads(res_rakuten.text)

user_states = {}
df = pd.DataFrame(columns=['category1','category2','category3','categoryId','categoryName'])
df_keyword = pd.DataFrame()
last_category_search = ''
first_choice = False
second_choice = False
empty_search = False
parent_dict = {}
print('starting database')
#df = pd.DataFrame(columns=['category1','category2','category3','categoryId','categoryName'])

# 大カテゴリ
for category in rakuten_data['result']['large']:
    df = df._append({'category1':category['categoryId'],'category2':"",'category3':"",'categoryId':category['categoryId'],'categoryName':category['categoryName']}, ignore_index=True)
# 中カテゴリ
for category in rakuten_data['result']['medium']:
    df = df._append({'category1':category['parentCategoryId'],'category2':category['categoryId'],'category3':"",'categoryId':str(category['parentCategoryId'])+"-"+str(category['categoryId']),'categoryName':category['categoryName']}, ignore_index=True)
    parent_dict[str(category['categoryId'])] = category['parentCategoryId']
# 小カテゴリ
for category in rakuten_data['result']['small']:
    df = df._append({'category1':parent_dict[category['parentCategoryId']],'category2':category['parentCategoryId'],'category3':category['categoryId'],'categoryId':parent_dict[category['parentCategoryId']]+"-"+str(category['parentCategoryId'])+"-"+str(category['categoryId']),'categoryName':category['categoryName']}, ignore_index=True)
print('finished database')

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def response_message(event):
    # notesのCarouselColumnの各値は、変更してもらって結構です。
    # global df, df_keyword, last_category_search, first_choice, second_choice, empty_search
    global user_states
    user_id = event.source.user_id
    input_text = str(event.message.text)
    if user_id not in user_states:
        user_states[user_id] = {
            'df': pd.DataFrame(columns=['category1','category2','category3','categoryId','categoryName']),
            'df_keyword': pd.DataFrame(),
            'last_category_search': input_text,
            #'first_choice': False,
            'category_selected': False,
            #'empty_search': False
        }
    else:
        user_states[user_id]['last_category_search'] = input_text
    df_keyword = user_states[user_id]['df_keyword']
    last_category_search = user_states[user_id]['last_category_search']
    #first_choice = user_states[user_id]['first_choice']
    category_selected = user_states[user_id]['category_selected']
    #empty_search = user_states[user_id]['empty_search']
    textArr = []
    print('last_category_search:', last_category_search, category_selected)
    if last_category_search.isnumeric() and category_selected:
        print('\nEntrou category_selected')
        category_ranking = requests.get(f'https://app.rakuten.co.jp/services/api/Recipe/CategoryRanking/20170426?applicationId=1043289948570835263&categoryId={df_keyword["categoryId"].values[int(input_text)-1]}')
        json_data_ranking = json.loads(category_ranking.text)
        myDBB = pd.DataFrame(columns=['foodImageUrl','mediumImageUrl','nickname','recipeCost', 'recipeDescription', 'rank', 'smallImageUrl', 'recipeUrl', 'recipeTitle'])
        for detail in json_data_ranking['result']:
            myDBB = myDBB._append({'foodImageUrl': detail['foodImageUrl'], 'mediumImageUrl': detail['mediumImageUrl'], 'nickname': detail['nickname'], 'recipeCost': detail['recipeCost'], 'recipeDescription': detail['recipeDescription'], 'rank': detail['rank'], 'smallImageUrl': detail['smallImageUrl'], 'recipeUrl': detail['recipeUrl'], 'recipeTitle': detail['recipeTitle']}, ignore_index=True)
        carousel_items = []
        for i, recipe in enumerate(myDBB["recipeUrl"], 1):
            carousel_column = {
                "thumbnail_image_url": f"{myDBB['foodImageUrl'][i-1]}",
                "title": f"{myDBB['recipeTitle'][i-1]}",
                "text": f"{myDBB['recipeDescription'][i-1][:59]}",  # Corrected the syntax here
                "actions": [
                    {"type": "uri", "label": "レシピURLへ", "uri": f"{myDBB['recipeUrl'][i-1]}"}
                ]
            }
            carousel_items.append(carousel_column)

        messages = TemplateSendMessage(
            alt_text='template',
            template=CarouselTemplate(columns=carousel_items),
        )

        line_bot_api.reply_message(event.reply_token, messages=messages)
        user_states[user_id]['category_selected'] = False
    else:
        print('searching category\n')
        df_keyword = df.query(f'categoryName.str.contains("{event.message.text}")', engine='python').copy()
        print('query result\n', df_keyword)
        df_keyword.drop_duplicates('categoryName', inplace=True)
        delete_row = df_keyword[df_keyword["categoryName"]==input_text].index
        df_keyword = df_keyword.drop(delete_row).iloc[:5]
        user_states[user_id]['df_keyword'] = df_keyword
        if df_keyword.empty:
            print('entrou empty\n')
            textArr.append('レシピは見つかりませんでした！')
            user_states[user_id]['category_selected'] = False
        else:
            print('Make user choose category')
            for i, category in enumerate(df_keyword["categoryName"], 1):
                if i==1:
                    textArr.append("レシピのカテゴリー（番号）を選択してください：")
                textArr.append(f"{i} - {category}")
            user_states[user_id]['category_selected'] = True
        line_bot_api.reply_message(event.reply_token, messages=[TextMessage(text='\n\n'.join(textArr))] )

if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=LineBotSdkDeprecatedIn30)
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
