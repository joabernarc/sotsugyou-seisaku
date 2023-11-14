import os

import requests
import json
import pandas as pd

from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.v3.messaging import (
    Configuration
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TemplateSendMessage, CarouselTemplate, CarouselColumn)

app = Flask(__name__)

access_token='cl2ehA91yxD/3uJRzDyls9SlRQTcprQVs7wRkMxog6d8LQK1+L9Z4SWnQoUukY5C8JNjml7xLrON9D7RMDfDeKyov5+tQ7WuSsA/5kTAB+5BgR/+7t9FIGzr/IqWu9Z9Guv9vzP526VC43HDjtOdWAdB04t89/1O/w1cDnyilFU='

line_bot_api = LineBotApi(access_token)
handler = WebhookHandler('3879d5592c6cff489b2ce1540972e4de')
res_rakuten = requests.get('https://app.rakuten.co.jp/services/api/Recipe/CategoryList/20170426?applicationId=1043289948570835263')
rakuten_data = json.loads(res_rakuten.text)
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


@handler.add(MessageEvent, message=TextMessage)
def response_message(event):
    # notesのCarouselColumnの各値は、変更してもらって結構です。
    global df, df_keyword, last_category_search, first_choice, second_choice, empty_search
    input_text = str(event.message.text)
    if not input_text.isnumeric():
        last_category_search = event.message.text
        df_keyword = df.query(f'categoryName.str.contains("{event.message.text}")', engine='python')
        print('query result', df_keyword)
        df_keyword.drop_duplicates('categoryName', inplace=True)
        delete_row = df_keyword[df_keyword["categoryName"]==input_text].index
        df_keyword = df_keyword.drop(delete_row).iloc[:5]

    myArr2 = []
    textArr = []
    if df_keyword.empty:
        textArr.append('Sorry, no recipe found!')
        first_choice = False
        second_choice = False
        empty_search = True
    else:
        first_choice = not second_choice
    for i, category in enumerate(df_keyword["categoryName"], 1):
        #print('@E NUMERO??', input_text.isnumeric())
        if i==1:
            textArr.append("Choose a recipe category:")
        textArr.append(f"{i} - {category}")

    if first_choice|empty_search:
        print('Make user choose category')
        messages = TextMessage(text='\n\n'.join(textArr))
        line_bot_api.reply_message(event.reply_token, messages=[TextMessage(text='\n\n'.join(textArr))] )
        if empty_search:
            first_choice = True
            second_choice = False
            empty_search = False
        else:
            first_choice = False
            second_choice = True



    elif second_choice:
        category_ranking = requests.get(f'https://app.rakuten.co.jp/services/api/Recipe/CategoryRanking/20170426?applicationId=1043289948570835263&categoryId={df_keyword["categoryId"].values[int(input_text)-1]}')
        json_data_ranking = json.loads(category_ranking.text)
        myDBB = pd.DataFrame(columns=['foodImageUrl','mediumImageUrl','nickname','recipeCost', 'recipeDescription', 'rank', 'smallImageUrl', 'recipeUrl', 'recipeTitle'])
        for detail in json_data_ranking['result']:
            #df = df._append({'category1':category['categoryId'],'category2':"",'category3':"",'categoryId':category['categoryId'],'categoryName':category['categoryName']}, ignore_index=True)
            myDBB = myDBB._append({'foodImageUrl': detail['foodImageUrl'], 'mediumImageUrl': detail['mediumImageUrl'], 'nickname': detail['nickname'], 'recipeCost': detail['recipeCost'], 'recipeDescription': detail['recipeDescription'], 'rank': detail['rank'], 'smallImageUrl': detail['smallImageUrl'], 'recipeUrl': detail['recipeUrl'], 'recipeTitle': detail['recipeTitle']}, ignore_index=True)
        notes2 = []
        for i, recipe in enumerate(myDBB["recipeUrl"], 1):
            column = {
                "thumbnail_image_url": f"{myDBB['foodImageUrl'][i-1]}",
                "title": f"{myDBB['recipeTitle'][i-1]}",
                "text": f"{myDBB['recipeDescription'][i-1][:59]}",  # Corrected the syntax here
                "actions": [
                    {"type": "uri", "label": "レシピURLへ", "uri": f"{myDBB['recipeUrl'][i-1]}"}
                ]
            }
            notes2.append(column)
        notes = [CarouselColumn(thumbnail_image_url=myDBB['foodImageUrl'][0],
                                title=myDBB['recipeTitle'][0],
                                text=myDBB['recipeDescription'][0][:59],
                                actions=[{"type": "message","label": "レシピURLへ","text": f"{myDBB['recipeUrl'][0]}"}]),

                CarouselColumn(thumbnail_image_url=myDBB['foodImageUrl'][1],
                                title=myDBB['recipeTitle'][1],
                                text=myDBB['recipeDescription'][1][:59],
                                actions=[
                                    {"type": "message", "label": "レシピURLへ", "text": f"{myDBB['recipeUrl'][1]}"}]),

                CarouselColumn(thumbnail_image_url=myDBB['foodImageUrl'][2],
                                title=myDBB['recipeTitle'][2],
                                text=myDBB['recipeDescription'][2][:59],
                                actions=[
                                    {"type": "message", "label": "レシピURLへ", "text": f"{myDBB['recipeUrl'][2]}"}]),
                CarouselColumn(thumbnail_image_url=myDBB['foodImageUrl'][2],
                                title=myDBB['recipeTitle'][2],
                                text=myDBB['recipeDescription'][2][:59],
                                actions=[
                                    {"type": "message", "label": "レシピURLへ", "text": f"{myDBB['recipeUrl'][2]}"}])]
        messages = TemplateSendMessage(
            alt_text='template',
            template=CarouselTemplate(columns=notes2),
        )

        line_bot_api.reply_message(event.reply_token, messages=messages)
        second_choice = False

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
