# APRSFriendFinder

This service, written in Python, will be a bridge between your ARPS Position and Telegram. 
If you're en-route to your friend, theiy will get a Telegram notification, if you get close to them. 

All the APRS data originates from [APRS.fi](https://aprs.fi/).
Geocoding and travel time compuation is done by [OpenRouteService](https://openrouteservice.org/). 

To use this bot, rename the dotenv.txt file to .env and setup the file. You'll need to change:
 - API Key for ARPS
 - Your APRS SSID 
 - The Telegram Bot Token
 - The Open Route Service API 
 - The 'MAGIC_KEY', a 'password' so that the owner of the bot can be identified

The rest can be left as-is.

You can run this in a Docker container. For that use:
`docker build -t aprsfriendalert .`
`docker run -d -v /absoulte/path/to/this/repo:/usr/src/app aprsfriendalert`

There is no warranty whatsoever.