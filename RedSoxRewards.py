# Importing libraries
import requests
import json
import time
import logging
from logging.handlers import TimedRotatingFileHandler
import yaml

#Read Config File and set variables
with open("config.yaml", "r") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

# Log File
logger = logging.getLogger('RedSoxRewardsWatcher')
logger.setLevel(logging.DEBUG)
logname = "RedSoxRewardsWatcher.log"
handler = TimedRotatingFileHandler(logname, when="midnight", backupCount=30)
handler.suffix = "%Y%m%d"
date_format = "%Y-%m-%d %H:%M:%S"
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', date_format)
handler.setFormatter(formatter)
logger.addHandler(handler)

# Function to send message
def send_message(user_id, text):
    # This comes from BotFather
    url = config['telegram_url']
    
    params = {
      "chat_id": user_id,
      "text": text,
   }
    resp = requests.get(url, params=params)
    
    #Throw an exception if Telegram API fails
    resp.raise_for_status()

#Authenticate with site
def login(username, password, guid, portal):
    s = requests.Session()
    payload = {
        'LoginFields':{
        'username': username,
        'password': password,
        'deviceGUID': guid,
        'PortalUrl': portal
        }
    }
    
    # Send login info
    res = s.post('https://rewards.redsox.com/PortalProxy/api/token/mlbam', json=payload)
    logger.debug('Authentication Response %s', res)

    #Attempt to reauthenticate if api response is not 200 (success)
    while res.status_code != 200:
        logger.debug(f'Login response {res}, attempting to try again in 5 minutes.')
        time.sleep(300)
        res = s.post('https://rewards.redsox.com/PortalProxy/api/token/mlbam', json=payload)

    #Log api response for debugging
    logger.debug('Authentication Response Content: %s', res.content)
    token = json.loads(res.content)
    logger.debug('Authentication Token %s', token)
    tokens=token['Tokens']
    logger.debug('Tokens: %s', tokens)
    accesstoken='Bearer ' + tokens['AccessToken']
    logger.debug('Access Token: %s', accesstoken)
    s.headers.update({'authorization': accesstoken})
    logger.debug('S: %s', s)
    
    return s

session = login(config['username'], config['password'], config['guid'], 'https://rewards.redsox.com')
logger.debug('Session: %s', session)

# to compare item id counts and notify if there is a change
print("running")

#inital check
currentCount = session.get('https://rewards.redsox.com/PortalProxy/api/marketplace/items').json()
logger.info('Performing the initial check')
time.sleep(config['sleepTimer'])

#updated items check loop
while True:
    try:
        # get updated list of items
        logger.info('Checking for new items')
        newCount = session.get('https://rewards.redsox.com/PortalProxy/api/marketplace/items').json()
 
        # check if there are new items
        if currentCount and newCount:
            logger.debug('Starting Item Compare')
            # Extract 'Id' values from both responses
            first_ids = {item['Id'] for item in currentCount}
            second_ids = {item['Id'] for item in newCount}

            # Find new 'Id' values (present in the second response but not in the first)
            new_ids = second_ids - first_ids

            # Process the results
            if new_ids:
                logger.info(f"Number of new Ids found: {len(new_ids)}")
                # Set first line of Telegram message with count of new items
                messageHeader = f'Marketplace Updated: {len(new_ids)} new item(s) found'
                #Initialize varible to store the names of all new items
                allNewItems = ""
                #Check each new item for their display name
                for new_ids in new_ids:
                    displayname = None
                    for item in newCount:
                        if item['Id'] == new_ids:
                            displayname = item['DisplayName']
                            break
                    # If a display name is found add it to the all new items variable
                    if displayname is not None:
                        print(f'The display name of {new_ids} is {displayname}')
                        allNewItems = allNewItems + '\n' + displayname
                # Send Telegram message with number if new items and their associated display names
                send_message(config['user_id'], messageHeader + '\n' + allNewItems)
                time.sleep(config['sleepTimer'])
                currentCount = newCount
                continue
            else:
                logger.info("No new items found.")
                time.sleep(config['sleepTimer'])
                currentCount = newCount
                continue
        else:
            logger.debug('Main IF Sleep')
            time.sleep(config['sleepTimer'])
            continue
             
    # To handle exceptions
    except Exception as e:
        logger.error("error")
        logger.error(e)
        #raise SystemExit(0)
        session = login(config['username'], config['password'], config['guid'], 'https://rewards.redsox.com')
        logger.error('Reauth Needed')