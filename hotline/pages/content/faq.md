# FAQ

## What happens when I call a hotline?

1. You will be greeted with an automated message. :)
2. You'll be dropped into a new conference call.
3. The hotline will call all of the event's configured organizers.
4. When an event member picks up, they're connected to the call and their name is announced to you.

The organizers *never* see your phone number. They only see the hotline's number.


## What happens when I text a hotline?

1. You'll be greeted with an automated message. :)
2. The hotline will create a "virtual group chat" with you an the organizers. Any message you send to the hotline will be relayed to the organizers.
3. The hotline will notify the organizers via text that a reporter has contacted them using a *unique relay number*.
4. The organizers can respond to the chat relay number to have their message relayed to you and the other members.

The organizers *never* see your phone number. They only see the unique relay number.


## Do you collect any information?

We keep an audit and error log. The audit log *does* keep track of your phone number if you call the hotline, but the number **is not** visible to event organizers (instead, an anonymized UUID is shown). We keep track on numbers in the database in case we need to **block** an abusive number - but we can do this without revealing the number to the organizers. We also have to cooperate with any subpeonas for records, so it is possible that your number may be turned over as part of a subpeona response.

See our [privacy policy](/pages/privacy) for more details.


## Who built this?

[Thea Flowers](https://thea.codes) built this with lots of inspiration from [Mariatta's](https://mariatta.ca) [enhanced CoC hotline](https://www.nexmo.com/blog/2018/11/15/pycascades-code-of-conduct-hotline-nexmo-voice-api-dr/).


## What's it built with?

Lots of stuff!

* [Python 3](https://python.org)
* [Flask](http://flask.pocoo.org/)
* [PostgreSQL](https://www.postgresql.org/)
* [peewee](http://docs.peewee-orm.com)
* [Firebase Authentication](https://firebase.google.com/docs/auth/)
* [Nexmo](https://nexmo.com)
* [cmarkgfm](https://pypi.org/project/cmarkgfm)

& more!

## Where's the source code?

[GitHub](https://github.com/theacodes/conducthotline.com).

## Who pays for this?

[Thea Flowers](https://thea.codes) (me). I offer this as a free service to any events that want to use it. It's not expensive, but it's also not free, either. If you want you can [donate](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=E9R6P8RVSRHSS&currency_code=USD&source=url).


## Where is this hosted?

It's hosted on [Google Cloud Platform](https://cloud.google.com) using Python 3 on Google App Engine and PostgreSQL on Google Cloud SQL.


## What telephony provider do you use?

It uses [Nexmo](https://nexmo.com).

