from pymongo import MongoClient
import datetime
import time
import urllib
import json

app_id = "443809049300463"
app_secret = "e6ff2a431bb3da7624faefbf39a15a3d" # DO NOT SHARE WITH ANYONE!

access_token = app_id + "|" + app_secret

client = MongoClient()
db = client.meme_scrape


def request_until_succeed(url):
    req = urllib.request.Request(url)
    success = False
    while success is False:
        try:
            response = urllib.request.urlopen(req)
            if response.getcode() == 200:
                success = True
        except Exception as e:
            print(e)
            time.sleep(5)

            print("Error for URL %s: %s" % (url, datetime.datetime.now()))

    return response.read()


def processFacebookPageFeedStatus(post):
    """
        Formats a post--helper function for scrapeFacebookPageFeedStatus.
    """

    post_id = post['id']
    post_message = '' if 'message' not in post.keys() else post['message'].encode('utf-8')
    link_name = '' if 'name' not in post.keys() else post['name'].encode('utf-8')
    post_type = post['type']
    post_link = '' if 'link' not in post.keys() else post['link']
    poster_id = post['from']['id']
    poster_name = post['from']['name']


    # Time needs special care since a) it's in UTC and
    # b) it's not easy to use in statistical programs.

    post_published = datetime.datetime.strptime(post['created_time'],'%Y-%m-%dT%H:%M:%S+0000')
    post_published = post_published + datetime.timedelta(hours=-8) # PST
    post_published = post_published.strftime('%Y-%m-%d %H:%M:%S') # best time format for spreadsheet programs

    update_time = datetime.datetime.strptime(post['updated_time'],'%Y-%m-%dT%H:%M:%S+0000')
    update_time = update_time + datetime.timedelta(hours=-8) # PST

    # Nested items require chaining dictionary keys.

    num_likes = 0 if 'likes' not in post.keys() else post['likes']['summary']['total_count']
    num_comments = 0 if 'comments' not in post.keys() else post['comments']['summary']['total_count']
    num_shares = 0 if 'shares' not in post.keys() else post['shares']['count']

    # return a tuple of all processed data
    return (post_id, post_message, poster_id, poster_name, link_name, post_type, post_link,
           post_published, num_likes, num_comments, num_shares, update_time)


def scrapeFacebookPageFeedStatus(page_id, access_token):
    """
        Exports all posts for the page to a csv.
    """

    with open('%s_facebook_statuses.csv' % page_id, 'w') as file:
        w = csv.writer(file)
        w.writerow(["post_id", "post_message", "poster_id", "poster_name",
                    "link_name", "post_type", "post_link", "post_published",
                    "num_likes", "num_comments", "num_shares", "update_time"])

        has_next_page = True
        num_processed = 0   # keep a count on how many we've processed
        scrape_starttime = datetime.datetime.now()

        print("Scraping %s Facebook Page: %s\n" % (page_id, scrape_starttime))

        statuses = getFacebookPageFeedData(page_id, access_token, 100)

        while has_next_page:
            for status in statuses['data']:
                info = processFacebookPageFeedStatus(status)
                w.writerow(info)

                # output progress occasionally to make sure code is not stalling
                num_processed += 1
                if num_processed % 1000 == 0:
                    print("%s Statuses Processed: %s" % (num_processed, datetime.datetime.now()))

            # if there is no next page, we're done.
            if 'paging' in statuses.keys():
                statuses = json.loads(request_until_succeed(statuses['paging']['next']).decode('utf-8'))
            else:
                has_next_page = False


        print("\nDone!\n%s Posts Processed in %s" % (num_processed, datetime.datetime.now() - scrape_starttime))


def parseAllReactions(post_id, num_reactions):
    """
        Input: post_id, num_reactions -- the size of each page of reactions
        Upserts a user to the meme_scraper.user_reactions database and their reaction to a
        certain post in type, post_id dictionaries.
        MUTATES DATABASE
    """
    base = "https://graph.facebook.com/v2.8/"+post_id+"/reactions"
    parameters = "?access_token=%s&limit=%s" % (access_token, num_reactions)

    url = base + parameters

    scrape_starttime = datetime.datetime.now()
    data = json.loads(request_until_succeed(url).decode('utf-8'))

    post_data = []
    pages = 0
    has_next_page = True

    while has_next_page:
        post_data = post_data + data['data']
        for i in data['data']:
            db.user_reactions.update_one( { "_id": i['id'] } ,
                                        { "$push": { 'reactions' : {'type' : i['type'], 'post_id' : post_id} } }, upsert = True)
            db.user_id.update_one( { "_id": i['id'] } ,
                                        { "$set": { 'name' : i['name'] } }, upsert = True)
        pages+=1
        # if there is no next page, we're done.
        if 'next' in data['paging'].keys():
            data = json.loads(request_until_succeed(data['paging']['next']).decode('utf-8'))
        else:
            has_next_page = False

    db.post_reactions.insert_one( {'_id' : post_id, 'reactions' : post_data} )
    print("\nDone!\n%s pages Processed in %s" % (pages, datetime.datetime.now() - scrape_starttime))


def getNameFromId(user_id):
    url = "https://graph.facebook.com/v2.9/" + user_id + "?access_token=" + access_token
    name = json.loads(request_until_succeed(url).decode('utf-8'))['name']

    return name


def formatUserReactions(user_id):
    """
        After parsing with parseAllReactions, reformats the reactions
        of a single user into a more readable format.
        Returns two things--a list of posts they've reacted to and
        their reactions to those posts.
    """

    user = db.user_reactions.find({"_id" : user_id})
    if not any(True for _ in user):
        print("No reaction data for:", getNameFromId(user_id), "(ID: " + user_id + ")")
        return

    posts = []
    reactions = []
    for i in user['reactions']:
        posts = posts + [i['post_id']]
        reactions = reactions + [i['type']]

    #     db.user_reactions.update_one( { "_id": user_id } ,
    #                     { "$set": { 'posts_liked' : posts , 'reaction_breakdown' : reactions } }, upsert = True)

    return posts, reactions
