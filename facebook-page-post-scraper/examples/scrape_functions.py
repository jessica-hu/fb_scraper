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


def scrapeFacebookPageFeedStatus(page_id, access_token):
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


        print("\nDone!\n%s Statuses Processed in %s" % (num_processed, datetime.datetime.now() - scrape_starttime))

def processFacebookPageFeedStatus(post):

    # The status is now a Python dictionary, so for top-level items,
    # we can simply call the key.

    # Additionally, some items may not always exist,
    # so must check for existence first

    # Fields: post_id, post_message, from,

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
