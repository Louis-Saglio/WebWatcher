import datetime
import os
import random
import string

import peewee
from flask import Flask, jsonify, abort, request

# Model


os.remove(':test:')
db = peewee.SqliteDatabase(':test:')


class WebSite(peewee.Model):
    domain_name = peewee.CharField()

    def __repr__(self):
        return str(self.domain_name)

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

for _ in range(20):
    WebSiteStatusLog(
        web_site=WebSite.create(domain_name=''.join(random.sample(string.ascii_letters, 1))),
        date=datetime.datetime.now(),
        status=random.randint(200, 550)
    ).save()


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
    return jsonify({'web_sites': [web_site.domain_name for web_site in WebSite.select()]})


@app.route('/add-web-site', methods={'POST'})
def add_web_site():
    WebSite(domain_name=request.form['domain_name']).save()
    return 'created', 201


@app.route('/remove-web-site/<string:domain-name>', methods={'DELETE'})
def remove_web_site(domain_name: str):
    pass


if __name__ == '__main__':
    app.run()
