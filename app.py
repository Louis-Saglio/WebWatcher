import datetime
import hashlib
import multiprocessing
import os
import time

import peewee
import requests
from flask import Flask, abort, request, render_template, redirect, flash

import conf

LOGIN_MESSAGE = 'You must login before accessing this url.'

# Model

db = peewee.SqliteDatabase('db.sqlite')


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
os.chmod('db.sqlite', 0o766)


# Background script

def check_status():
    # Cannot fail so it will always be active and will never die, until the server dies (feature).
    while True:
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
                                    print(mock_api)  # simulate api call
                                    # I don't want to create account on Slack and Telegram and you have no right to force me to do this
                                    Message.create(web_site=web_site, date=datetime.datetime.now())
                            except BaseException as e:
                                print(e)
                except BaseException as e:
                    print(e)
        except BaseException as e:
            print(e)
        time.sleep(120)


multiprocessing.Process(target=check_status).start()


# Controller

app = Flask('WebWatcher')  # config
app.secret_key = 'secret key'


@app.route('/web-site/<int:id_>')
def get_statuses(id_: int):
    web_sites = WebSiteStatusLog.select().join(WebSite).where(WebSite.id == id_)
    if not web_sites:
        flash('Encore aucun log')
        return redirect('/')
    logs = []
    for log in web_sites:
        logs.append(log.as_dict())
    return render_template('get_statuses.html', logs=logs)


@app.route('/')
def list_web_sites():
    return render_template('index.html', web_sites=[(web_site.url, web_site.id) for web_site in WebSite.select()])


@app.route('/add-web-site', methods={'POST', 'GET'})
def add_web_site():
    if not request.form:
        return render_template('add_web_site.html')
    if request.cookies.get('admin') == 'True':
        WebSite.create(url=request.form['url'])
        flash('Web site with url : {} has been successfully created'.format(request.form['url']))
    else:
        flash(LOGIN_MESSAGE)
    return redirect('/')


@app.route('/remove-web-site/<int:id_>', methods={'GET'})
def remove_web_site(id_: int):
    if request.cookies.get('admin') == 'True':
        WebSite.delete_instance(WebSite.get_by_id(id_), recursive=True)
        flash('Website deleted')
    else:
        flash(LOGIN_MESSAGE)
    return redirect('/')


@app.route('/update-web-site/<int:id_>', methods={'GET', 'POST'})
def update_website(id_: int):
    if not request.form:
        return render_template('update.html', id=id_)
    if request.cookies.get('admin') == 'True':
        WebSite.update(url=request.form['url']).where(WebSite.id == id_).execute()
        flash('Website updated')
    else:
        flash(LOGIN_MESSAGE)
    return redirect('/')


@app.route('/login', methods={'GET', 'POST'})
def login():
    if not request.form:
        return render_template('login.html')
    resp = redirect('/')
    password = request.form.get('password', '') if request.method == 'POST' else request.args.get('password', '')
    if hashlib.sha256(bytes(password, encoding='utf-8')).hexdigest() == conf.PASSWORD:
        resp.set_cookie('admin', 'True')
        flash('Authenticated')
    else:
        flash('Failed')
        resp.set_cookie('admin', 'False')
    return resp


if __name__ == '__main__':
    app.run('127.0.0.1', 8800)
