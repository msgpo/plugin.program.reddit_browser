# -*- coding: utf-8 -*-

'''
    License summary below, for more details please read license.txt file

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 2 of the License, or
    (at your option) any later version.
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import json, time, platform, pyxbmct
from re import sub as substitute
from resources.lib.modules.tools import available_domains, add_to_history, history_subrs, history_media, get_ip
from tulip import control, client
from tulip.log import log_debug
from tulip.compat import quote_plus, quote, BaseHTTPServer, ThreadingMixIn
from resources.lib.modules.tools import convert_date, saved_subrs, refresh


dotjson = '{0}'.format('' if control.setting('access.token') else '.json')
client_id = 'WRtrShlQM3Boug'
state = 'redditbrowser'

redirect_uri = 'http://{0}:{1}/'.format('127.0.0.1', '50201')
scope = ['identity', 'read', 'mysubreddits', 'save', 'history', 'subscribe']


def user_agent():

    UA = '{0} {1}:Reddit Browser:v{2} (by /u/tvaddonsdotco)'.format(
        platform.system(), platform.release(), control.version()
    )

    return UA


def base_link(override=False):

    base = 'www' if not control.setting('access.token') or override else 'oauth'

    return 'https://{0}.reddit.com'.format(base)


def api_link(end_point):

    return '{0}/api/v1/{1}'.format(base_link(override=True), end_point)


def authorization_link(compact=control.setting('compact.page') == 'true'):

    return api_link(
        'authorize{0}?client_id={1}&response_type=code&state={2}&redirect_uri={3}&duration=permanent&scope={4}'.format(
            '.compact' if compact else '', client_id, state, redirect_uri, ','.join(scope)
        )
    )


def reddit_url(end_point):

    link = base_link() + end_point

    return link


def request_headers():

    headers = {'User-Agent': user_agent(), 'Authorization': 'bearer ' + control.setting('access.token'), 'raw_json': '1'}

    return headers


def url_generator(query='', media=True, advanced=False, history=False, domain=False):

    search_link = base_link() + '/search{0}?q={1}' if not domain else base_link() + '/domain/{0}/{1}'
    sr_search_link = base_link() + '/subreddits/search{0}?q={1}'
    subreddit = 'subreddit:'  # find submissions in "subreddit"
    author = 'author:'  # find submissions by "username"

    site = 'site:'  # find submissions from "example.com"
    url = 'url:'  # search for "text" in url
    selftext = 'selftext:'  # search for "text" in self post contents
    self_search = 'self:{0}'  # Set to yes for text submissions, no otherwise. 1 and 0 are also supported.
    flair = 'flair:""'

    items_limit = '&limit=' + control.setting('items.limit')  # numbered string
    if domain:
        items_limit = items_limit.replace('&', '?')

    if control.setting('include.nsfw') == 'true' and control.setting('access.token') and control.setting('nsfw.toggle') == 'true':  # include (or exclude) results marked as NSFW
        nsfw = 'nsfw:1'
    else:
        nsfw = ''

    nsfw_query = ' ' + nsfw if nsfw else ''

    # Operators used by reddit:
    # OR = 'OR'
    # NOT = 'NOT'
    # AND = 'AND'

    if not media:

        if not query:

            query = control.dialog.input(control.name(), nsfw_query)

            if not query:
                return

        if control.setting('history.bool') == 'true' and not history:
            add_to_history(query, history_subrs)

        output = sr_search_link.format(dotjson, quote_plus(query) + items_limit)

        return output

    else:

        if advanced:

            choices = [
                control.lang(30014), control.lang(30019), control.lang(30020), control.lang(30022), control.lang(30052),
                control.lang(30119), control.lang(30053),
                control.lang(30054 if control.setting('add.hosts') == 'true' else 30021)
            ]

            generate = [nsfw, subreddit, author, url, self_search.format('no'), flair, selftext, site]

            if control.setting('include.nsfw') == 'false':
                del choices[0]
                del generate[0]

            indices = control.dialog.multiselect(control.lang(30018), choices)

            if not indices or indices == [-1]:

                return

            else:

                generated = [generate[i] for i in indices]

                joined = ' '.join(generated)

                if control.setting('add.hosts') == 'true':
                    joined = joined.replace('site:', '')

                q = control.dialog.input(control.name(), ' ' + joined)

                if not q or q == ' ':
                    return

                if control.setting('add.hosts') == 'true' and 7 in indices:
                    q += ' ' + site + available_domains()

                output = search_link.format(
                    dotjson, quote_plus(q) + items_limit
                )

                if control.setting('history.bool') == 'true':
                    add_to_history(q, history_media)

                return output

        else:

            if not query:

                query = control.dialog.input(control.name())

                if not query:
                    return

            if not domain:

                if 'self:yes' in query or 'self:1' in query:
                    self = self_search.format('yes')
                else:
                    self = self_search.format('no')

                if control.setting('add.hosts') == 'true':
                    query += ' ' + self + nsfw_query + ' ' + site + available_domains()
                else:
                    query += ' ' + self + nsfw_query

                if control.setting('history.bool') == 'true' and not history:
                    add_to_history(query, history_media)

                output = search_link.format(
                    dotjson, quote_plus(query) + items_limit
                )

                return output

            else:

                output = search_link.format(query + items_limit)

                return output


def reddit_subs(action, sr_name):

    if action is None:
        action = 'sub'
        sleep = True
    else:
        sleep = False

    if sr_name is None:
        from tulip.bookmarks import get
        bookmarks = get(file_=saved_subrs)
        if not bookmarks:
            return
        sr_name = ','.join([i['sr_name'] for i in bookmarks])

    post_data = {'action': action, 'sr_name': sr_name}

    result = client.request(base_link() + '/api/subscribe', post=post_data, headers=request_headers(), output='response')

    if control.setting('debugging.toggle') == 'true':
        log_debug(result)

    if action == 'unsub' or sleep:

        if sleep:
            control.sleep(100)

        control.refresh()


def reddit_save(action, thing_id):

    url = reddit_url('/api/{0}'.format(action))

    post_data = {'id': thing_id}

    response = client.request(url, post=post_data, output='extended', headers=request_headers())

    if control.setting('debugging.toggle') == 'true':
        log_debug(response)

    if action == 'unsave':
        refresh()


def multisel(subreddits, simple=False):

    if not simple:

        listed = [i.get('name') for i in json.loads(subreddits)]

        indices = control.dialog.multiselect(control.lang(30072), listed)

        if not indices:

            return

        else:

            names = [listed[i] for i in indices]

            joined = '+'.join(names)

            output = reddit_url('/r/' + joined + '/')

            return output

    else:

        output = reddit_url('/r/' + subreddits + '/')

        return output


class QR_display(pyxbmct.AddonDialogWindow):

    pyxbmct.skin.estuary = control.setting('pyxbmct.estuary') == 'true'

    link = 'https://is.gd/standard_auth' if control.setting('compact.page') == 'false' else 'https://is.gd/compact_auth'

    geometry = (542, 286, 6, 2)

    def __init__(self, title):

        super(QR_display, self).__init__(title)
        self.image = None
        self.text_box = None
        self.link_button = None
        self.close_button = None
        self.address_button = None
        self.server_button = None
        self.setGeometry(*self.geometry)
        self.set_controls()
        self.set_navigation()
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)

    def set_controls(self):

        # Image object
        self.image = pyxbmct.Image(
            'http://chart.apis.google.com/chart?cht=qr&chl={0}&chs=256'.format(quote(authorization_link())),
            aspectRatio=2
        )
        self.placeControl(self.image, 0, 0, 6)
        # Text box
        self.text_box = pyxbmct.TextBox()
        self.placeControl(self.text_box, 0, 1, 2)
        self.text_box.setText(control.lang(30064).format(get_ip()))
        self.text_box.autoScroll(1000, 1000, 1000)
        # Button capable of changing the local ip address
        self.address_button = pyxbmct.Button(control.lang(30056))
        self.placeControl(self.address_button, 2, 1)
        self.connect(self.address_button, lambda: ip_address_set())
        # Button capable of starting the server
        self.server_button = pyxbmct.Button(control.lang(30147))
        self.placeControl(self.server_button, 3, 1)
        self.connect(self.server_button, lambda: reddit_server())
        # Button displaying address for auth, and capable of opening it
        self.link_button = pyxbmct.Button(self.link)
        self.placeControl(self.link_button, 4, 1)
        self.connect(self.link_button, lambda: control.open_web_browser(self.link))
        # Close button
        self.close_button = pyxbmct.Button(control.lang(30062))
        self.placeControl(self.close_button, 5, 1)
        self.connect(self.close_button, self.close)

    def set_navigation(self):

        self.address_button.controlDown(self.server_button)
        self.server_button.controlUp(self.address_button)
        self.server_button.controlDown(self.link_button)
        self.link_button.controlUp(self.server_button)
        self.link_button.controlDown(self.close_button)
        self.close_button.controlUp(self.link_button)
        self.setFocus(self.close_button)


def kodi_auth():

    aspect_ratio = control.infoLabel('Skin.AspectRatio')

    def obtain_authorization(_cookie, _uh):

        from tulip.compat import parse_qsl, urlparse

        data = {
            'authorize': 'Allow', 'state': state, 'redirect_uri': redirect_uri, 'response_type': 'code',
            'client_id': client_id, 'duration': 'permanent', 'scope': ' '.join(scope), 'uh': _uh
        }

        headers = client.request(api_link('authorize'), cookie=_cookie, post=data, redirect=False, output='headers')

        geturl = dict([line.partition(': ')[::2] for line in str(headers).splitlines()]).get('location')

        token = dict(parse_qsl(urlparse(geturl).query)).get('code')

        if not token:

            return

        get_tokens(code=token)

    class Prompt(pyxbmct.AddonDialogWindow):

        pyxbmct.skin.estuary = control.setting('pyxbmct.estuary') == 'true'

        if aspect_ratio == '4:3':
            geometry = (506, 380, 5, 5)
        else:
            geometry = (676, 380, 5, 5)

        def __init__(self, title, description, _cookie, _uh):

            super(Prompt, self).__init__(title)
            self.allow_button = None
            self.deny_button = None
            self.text_box = None
            self.text = description
            self.cookie = _cookie
            self.uh = _uh
            self.setGeometry(*self.geometry)
            self.set_controls()
            self.set_navigation()
            self.connect(pyxbmct.ACTION_NAV_BACK, self.close)

        def set_controls(self):

            # Text box
            self.text_box = pyxbmct.TextBox()
            self.placeControl(self.text_box, 0, 0, 4, 5)
            self.text_box.setText(self.text)
            self.text_box.autoScroll(1000, 1000, 1000)
            # Allow
            self.allow_button = pyxbmct.Button(control.lang(30150))
            self.placeControl(self.allow_button, 4, 1)
            self.connect(self.allow_button, lambda: self.authorize())
            # Deny
            self.deny_button = pyxbmct.Button(control.lang(30151))
            self.placeControl(self.deny_button, 4, 3)
            self.connect(self.deny_button, self.close)

        def set_navigation(self):

            self.allow_button.controlRight(self.deny_button)
            self.deny_button.controlLeft(self.allow_button)
            self.setFocus(self.allow_button)

        def authorize(self):

            obtain_authorization(self.cookie, self.uh)
            self.close()

    class UserPass(pyxbmct.AddonDialogWindow):

        pyxbmct.skin.estuary = control.setting('pyxbmct.estuary') == 'true'

        if aspect_ratio == '4:3':
            geometry = (341, 256, 5, 1)
        else:
            geometry = (455, 256, 5, 1)

        def __init__(self, title):

            super(UserPass, self).__init__(title)
            self.username_label = None
            self.user_input = None
            self.password_label = None
            self.pass_input = None
            self.submit_button = None
            self.setGeometry(*self.geometry)
            self.set_controls()
            self.set_navigation()
            self.connect(pyxbmct.ACTION_NAV_BACK, self.close)

        def set_controls(self):

            # Username label
            self.username_label = pyxbmct.Label(control.lang(30152))
            self.placeControl(self.username_label, 0, 0)
            # Username input
            self.user_input = pyxbmct.Edit(control.lang(30152))
            self.placeControl(self.user_input, 1, 0)
            # Password label
            self.password_label = pyxbmct.Label(control.lang(30153))
            self.placeControl(self.password_label, 2, 0)
            # Password input
            self.pass_input = pyxbmct.Edit(control.lang(30153), isPassword=True)
            self.placeControl(self.pass_input, 3, 0)
            # Close button
            self.submit_button = pyxbmct.Button(control.lang(30154))
            self.placeControl(self.submit_button, 4, 0)
            self.connect(self.submit_button, lambda: self.submit(True))

        def set_navigation(self):

            self.user_input.controlDown(self.pass_input)
            self.pass_input.controlUp(self.user_input)
            self.pass_input.controlDown(self.submit_button)
            self.submit_button.controlUp(self.pass_input)
            self.setFocus(self.user_input)

        def credentials(self):

            return self.user_input.getText(), self.pass_input.getText()

        def submit(self, _submitted=False):

            if _submitted:

                self.close()

                return True

    userpass_window = UserPass(control.name())
    userpass_window.doModal()

    username, password = userpass_window.credentials()

    if not username or not password:

        return

    login_url = base_link(True) + '/api/login/' + username

    data = {
        'form_is_compact': 'true', 'dest': authorization_link(True), 'passwd': password, 'user': username, 'rem': 'on',
        'api_type': 'json', 'op': 'login'
    }

    del userpass_window

    cookie = client.request(login_url, close=False, post=data, output='cookie')

    html = client.request(authorization_link(True), cookie=cookie)

    uh = client.parseDOM(html, 'input', attrs={'name': 'uh'}, ret='value')[0]
    permissions = client.parseDOM(html, 'div', attrs={'class': 'access-permissions'})[0]
    notice = client.parseDOM(html, 'p', attrs={'class': 'notice'})[0]

    text = client.replaceHTMLCodes(client.stripTags(permissions + '[CR]' + notice))

    text = substitute(r'([.:]) ?', r'\1[CR]', text).partition('[CR]')

    prompt_window = Prompt(title=text[0], description=text[2], _cookie=cookie, _uh=uh)
    prompt_window.doModal()

    del prompt_window


def ip_address_set():

    yesno = control.yesnoDialog(control.lang(30060), yeslabel='127.0.0.1', nolabel=get_ip())

    if yesno:

        control.setSetting('ip.address', '127.0.0.1')

    else:

        control.setSetting('ip.address', get_ip())


def authorize():

    control.setSetting('get.toggle', 'true')

    choices = [control.lang(30063), control.lang(30080), control.lang(30149), control.lang(30081)]

    choice = control.selectDialog(choices, control.lang(30061))

    if choice == 0:

        control.open_web_browser(authorization_link())
        reddit_server()

    elif choice == 1:

        window = QR_display(control.name())

        window.doModal()

        del window

    elif choice == 2:

        kodi_auth()

    elif choice == 3:

        control.okDialog(control.name(), control.lang(30146).format(QR_display.link))

        if control.setting('ip.address') == '0.0.0.0':
            ip_address_set()

        auth_token = control.dialog.input(heading=control.lang(30082))

        if not auth_token:
            control.okDialog(control.name(), control.lang(30083))
            return
        else:
            control.setSetting('auth.token', auth_token)
            get_tokens(code=auth_token)


def account_info():

    url = reddit_url('/api/v1/me')

    json_obj = client.request(url, headers=request_headers())

    name = json.loads(json_obj)['name']
    icon_img = json.loads(json_obj)['icon_img']

    return {'name': name, 'icon_img': icon_img}


def get_tokens(code=None, refresh=False):

    if not code:
        code = control.setting('auth.token')

    if refresh:
        post_data = {'grant_type': 'refresh_token', 'refresh_token': control.setting('refresh.token')}
        if control.setting('debugging.toggle') == 'true':
            log_debug('Attempting to refresh access token...')
    else:
        post_data = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect_uri}
        if control.setting('debugging.toggle') == 'true':
            log_debug('Attempting to retrieve access token...')

    if control.setting('debugging.toggle') == 'true':
        log_debug(post_data)

    headers = {'User-Agent': user_agent()}
    username, password = (client_id, '')
    result = client.request(api_link('access_token'), post=post_data, headers=headers, username=username, password=password)

    tokens = json.loads(result)

    if control.setting('debugging.toggle') == 'true':
        log_debug(tokens)

    if 'error' in tokens:
        try:
            log_debug('Authorization failed, reason: ' + tokens.get('error'))
        except TypeError:
            log_debug('Failure in general!')
        tokens_reset()
        return

    control.setSetting('access.token', tokens['access_token'])
    control.setSetting('expiration.string', convert_date(int(time.time()) + int(tokens['expires_in'])))
    control.setSetting('expiration.stamp', str(time.time() + float(tokens['expires_in'])))

    if not refresh:
        control.setSetting('access.scope', tokens['scope'].replace(' ', ', '))
        control.setSetting('refresh.token', tokens['refresh_token'])
        control.infoDialog(control.lang(30402))
        control.refresh()
    elif refresh:
        control.infoDialog(control.lang(30145))

    control.setSetting('auth.toggle', 'false')


def tokens_reset():

    control.setSetting('auth.token', '')
    control.setSetting('refresh.token', '')
    control.setSetting('access.token', '')
    control.setSetting('access.scope', '')
    control.setSetting('expiration.string', '')
    control.setSetting('expiration.stamp', '')
    control.setSetting('get.toggle', 'false')
    control.setSetting('auth.toggle', 'true')
    control.setSetting('username.string', '')


def revoke():

    yesno = control.yesnoDialog(control.lang(30079))

    if yesno:

        post = {'token': control.setting('access.token')}
        headers = {'User-Agent': user_agent()}
        username, password = (client_id, '')
        result = client.request(
            api_link('revoke_token'), post=post, headers=headers, username=username, password=password,
            output='response'
        )

        if control.setting('debugging.toggle') == 'true':
            log_debug('Revoking tokens, response: ' + result[0])

        tokens_reset()

        control.refresh()


def reddit_page(authorized=False, token=''):

    auth_page = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
        "http://www.w3.org/TR/html4/loose.dtd">
<html>
    <head>
        <title>Reddit Browser</title>
    </head>
    <body>
        <div style="text-align: center;">
            <h1>Reddit Browser, {version}</h1>
            {line1}!<br>
            {token}<br>
            {line2}
        </div>
    </body>
</html>
    """

    if authorized:
        html = auth_page.format(
            version=control.lang(30070).format(control.version()).encode('utf-8'),
            token=control.lang(30069).format(token).encode('utf-8'),
            line1=control.lang(30402).encode('utf-8'),
            line2=control.lang(30065).encode('utf-8')
        )
    else:
        html = auth_page.format(
            version=control.lang(30070).format(control.version()).encode('utf-8'),
            token='',
            line1=control.lang(30067).encode('utf-8'),
            line2=control.lang(30068).encode('utf-8')
        )

    return html


class BaseServer(BaseHTTPServer.BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def _set_headers(self):

        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()

    def do_GET(self):

        from tulip.compat import urlparse, parse_qsl

        parsed = urlparse(self.path)
        params = dict(parse_qsl(parsed.query))

        self._set_headers()
        self.wfile.write(reddit_page(authorized='code' in params, token=params.get('code', '')))

        if 'code' in params:
            control.setSetting('auth.token', params['code'])
            get_tokens(code=params['code'])
        elif 'error' in params:
            control.setSetting('get.toggle', 'false')
            tokens_reset()

    def do_HEAD(self):

        self._set_headers()


class ThreadedServer(ThreadingMixIn, BaseHTTPServer.HTTPServer):

    allow_reuse_address = True


def reddit_server():

    if control.setting('debugging.toggle') == 'true':
        log_debug('Starting http server')

    ip_address = control.setting('ip.address')

    if ip_address == '0.0.0.0':
        ip_address = '127.0.0.1'

    server = ThreadedServer((ip_address, int(control.setting('ip.port'))), BaseServer)

    server.handle_request()

    if control.setting('debugging.toggle') == 'true':
        log_debug('Stopped http server')
