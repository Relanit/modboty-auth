import os
import time

from flask_pymongo import PyMongo
from flask import Flask, request, render_template
import requests
from cryptography.fernet import Fernet

app = Flask(__name__)
app.config['MONGO_URI'] = os.getenv('MONGO')
db = PyMongo(app).db

fernet = Fernet(os.getenv('KEY').encode())


@app.route('/api/v1/auth')
def index():
    code = request.args.get('code')
    scope = request.args.get('scope')

    error = ''
    if not code or scope != 'channel:read:subscriptions moderation:read channel:manage:broadcast channel:manage:polls channel:manage:predictions channel:read:polls channel:read:predictions channel:read:vips channel:manage:vips':
        error = 'неверные разрешения'

    token_data = requests.post(f'https://id.twitch.tv/oauth2/token?client_id={os.getenv("CLIENT_ID")}&client_secret={os.getenv("CLIENT_SECRET")}&code={code}&grant_type=authorization_code&redirect_uri=http://localhost:5000/api/v1/auth').json()

    if 'access_token' not in token_data:
        error = 'ошибка авторизации'
    elif set(scope.split()) != {'channel:manage:broadcast', 'channel:manage:polls', 'channel:manage:predictions', 'channel:manage:vips', 'channel:read:polls', 'channel:read:predictions', 'channel:read:subscriptions', 'channel:read:vips', 'moderation:read'}:
        error = 'неверные разрешения'

    if not error:
        user_data = requests.get('https://api.twitch.tv/helix/users', headers={'Authorization': f'Bearer {token_data["access_token"]}', 'Client-Id': os.getenv('CLIENT_ID')}).json()

        to_send = {
            'login': user_data['data'][0]['login'],
            'access_token': fernet.encrypt(token_data['access_token'].encode()).decode(),
            'refresh_token': fernet.encrypt(token_data['refresh_token'].encode()).decode(),
            'expire_time': time.time() + token_data['expires_in']
        }
        data = db.config.find_one({'_id': 1})
        if user_data['data'][0]['login'] not in data['channels']:
            error = 'канал не подключён к боту'

        if not error and [user for user in data.get('user_tokens', [{}]) if user.get('login', '') == user_data['data'][0]['login']]:
            db.config.update_one({'_id': 1, 'user_tokens.login': user_data['data'][0]['login']}, {'$set': {'user_tokens.$': to_send}})
        elif not error:
            db.config.update_one({'_id': 1}, {'$addToSet': {'user_tokens': to_send}})

    result = f'Произошла ошибка: {error}' if error else 'Авторизация прошла успешно'

    return render_template('index.html', result=result)


if __name__ == '__main__':
    app.run(debug=False)
