import datetime
import os
import time

import peewee
import requests
import multiprocessing
from flask import Flask, jsonify, abort, request

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


db.create_tables([WebSite, WebSiteStatusLog])
os.chmod('test', 777)

WebSite.create(url='http://www.put.com')


# Background script

def check_status():
    # Cannot fail so it will always be active and will never die, until the server dies (feature).
    while True:
        time.sleep(5)
        try:
            for site in WebSite.select():
                try:
                    status = requests.get(site.url).status_code
                except BaseException as e:
                    print(e)
                    continue
                try:
                    WebSiteStatusLog.create(
                        web_site=site,
                        date=datetime.datetime.now(),
                        status=status
                    )
                except BaseException as e:
                    print(e)
        except BaseException as e:
            print(e)
            raise


multiprocessing.Process(target=check_status).start()


# Controller

app = Flask('WebWatcher')  # config


@app.route('/web-site/<string:domain_name>')
def get_statuses(domain_name: str):
    web_sites = WebSiteStatusLog.select().join(WebSite).where(WebSite.domain_name == domain_name)
    if not web_sites:
        abort(404)
    rep = {'logs': []}
    for log in web_sites:
        rep["logs"].append(log.as_dict())
    return jsonify(rep)


@app.route('/')
def list_web_sites():
    return jsonify({'web_sites': [web_site.url for web_site in WebSite.select()]})


@app.route('/add-web-site', methods={'POST'})
def add_web_site():
    WebSite.create(url=request.form['url'])
    return 'created', 201


@app.route('/remove-web-site/<string:url>', methods={'GET'})
def remove_web_site(url: str):
    WebSite.delete_instance(WebSite.get(url == url))
    return 'deleted', 200


@app.route('/update-web-site/<string:url>', methods={'POST'})
def update_website(url: str):
    WebSite.update(url=request.form['url']).where(WebSite.url == url).execute()
    return 'updated', 200


if __name__ == '__main__':
    app.run('127.0.0.1', 8800)