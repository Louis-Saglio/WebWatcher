import datetime
import hashlib
import os
import time

import peewee
import requests
import multiprocessing
from flask import Flask, jsonify, abort, request, make_response, render_template
import conf

LOGIN_MESSAGE = 'You must login before. Send post or get with password variable in body at /login. Password is p455w0rd'

# Model

try:
    os.remove('test')
except FileNotFoundError:
    pass
db = peewee.SqliteDatabase('test')


class WebSite(peewee.Model):
    url = peewee.CharField()

    def __repr__(self):
        return str(self.url)

    class Meta:
        database = db


class WebSiteStatusLog(peewee.Model):
    web_site = peewee.ForeignKeyField(WebSite)
    date = peewee.DateTimeField()
    status = peewee.IntegerField()

    def as_dict(self):
        return {'web_site': str(self.web_site), 'date': str(self.date), 'status': str(self.status)}

    class Meta:
        database = db


class Message(peewee.Model):
    web_site = peewee.ForeignKeyField(WebSite)
    date = peewee.DateTimeField()

    class Meta:
        database = db


db.create_tables([WebSite, WebSiteStatusLog, Message])
os.chmod('test', 777)

WebSite.create(url='http://www.put.com')


# Background script

def check_status():
    # Cannot fail so it will always be active and will never die, until the server dies (feature).
    while True:
        time.sleep(120)
        try:
            for site in WebSite.select():
                try:
                    status = requests.get(site.url).status_code
                except BaseException as e:
                    status = 999
                try:
                    WebSiteStatusLog.create(
                        web_site=site,
                        date=datetime.datetime.now(),
                        status=status
                    )
                except BaseException as e:
                    print(e)
                try:
                    for web_site in WebSite.select():
                        last_logs = WebSiteStatusLog.select().where(WebSiteStatusLog.web_site == web_site)[-3:]
                        if len(last_logs) < 3:
                            continue
                        for w in last_logs:
                            if str(w.status).startswith('2'):
                                break
                        else:
                            mock_api = {
                                'token': conf.API_TOKEN,
                                'message': web_site.url + ' is broken'
                            }
                            try:
                                messages = Message.select().order_by(Message.date.desc())
                                if not messages or (datetime.datetime.now() - messages[0].date).total_seconds() >= 3600:
                                    print(mock_api)
                                    Message.create(web_site=web_site, date=datetime.datetime.now())
                            except BaseException as e:
                                print(e)  # simulate api call
                            # I don't want to create account on Slack and Telegram and you have no right to force me to do this
                except BaseException as e:
                    print(e)
        except BaseException as e:
            print(e)


multiprocessing.Process(target=check_status).start()


# Controller

app = Flask('WebWatcher')  # config


@app.route('/web-site/<int:id_>')
def get_statuses(id_: int):
    web_sites = WebSiteStatusLog.select().join(WebSite).where(WebSite.id == id_)
    if not web_sites:
        abort(404)
    rep = {'logs': []}
    for log in web_sites:
        rep["logs"].append(log.as_dict())
    return jsonify(rep)


@app.route('/')
def list_web_sites():
    return render_template('index.html', **{'web_sites': [web_site.url for web_site in WebSite.select()]})


@app.route('/add-web-site', methods={'POST'})
def add_web_site():
    if request.cookies.get('admin'):
        WebSite.create(url=request.form['url'])
        return 'created', 201
    else:
        return LOGIN_MESSAGE


@app.route('/remove-web-site/<int:id_>', methods={'GET'})
def remove_web_site(id_: int):
    if request.cookies.get('admin'):
        WebSite.delete_instance(WebSite.get_by_id(id_))
        return 'deleted', 200
    else:
        return LOGIN_MESSAGE


@app.route('/update-web-site/<int:id_>', methods={'POST'})
def update_website(id_: int):
    if request.cookies.get('admin'):
        WebSite.update(url=request.form['url']).where(WebSite.id == id_).execute()
        return 'updated', 200
    else:
        return LOGIN_MESSAGE


@app.route('/login', methods={'GET', 'POST'})
def login():
    resp = make_response('Failed')
    password = request.form.get('password', '') if request.method == 'POST' else request.args.get('password', '')
    if hashlib.sha256(bytes(password, encoding='utf-8')).hexdigest() == conf.PASSWORD:
        resp = make_response('Authenticated')
        resp.set_cookie('admin', 'True')
    return resp


if __name__ == '__main__':
    app.run('127.0.0.1', 8800)
