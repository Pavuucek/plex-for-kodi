import xbmc
import xbmcgui
import kodigui

from lib import colors
from lib import util
from lib import backgroundthread

from plexnet import plexapp, playlist, plexplayer

import busy
import musicplayer
import videoplayer
import dropdown
import windowutils
import opener
import search
import playersettings
import info


class EpisodeReloadTask(backgroundthread.Task):
    def setup(self, episode, callback):
        self.episode = episode
        self.callback = callback
        return self

    def run(self):
        if self.isCanceled():
            return

        if not plexapp.SERVERMANAGER.selectedServer:
            # Could happen during sign-out for instance
            return

        try:
            self.episode.reload(checkFiles=1)
            if self.isCanceled():
                return
            self.callback(self.episode)
        except:
            util.ERROR()


class EpisodesWindow(kodigui.ControlledWindow, windowutils.UtilMixin):
    xmlFile = 'script-plex-episodes.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'
    res = '1080i'
    width = 1920
    height = 1080

    THUMB_AR16X9_DIM = (657, 393)
    POSTER_DIM = (420, 630)

    EPISODE_PANEL_ID = 400
    LIST_OPTIONS_BUTTON_ID = 111

    OPTIONS_GROUP_ID = 200

    HOME_BUTTON_ID = 201
    SEARCH_BUTTON_ID = 202
    PLAYER_STATUS_BUTTON_ID = 204

    PROGRESS_IMAGE_ID = 250

    PLAY_BUTTON_ID = 301
    SHUFFLE_BUTTON_ID = 302
    OPTIONS_BUTTON_ID = 303
    INFO_BUTTON_ID = 304
    SETTINGS_BUTTON_ID = 305

    def __init__(self, *args, **kwargs):
        kodigui.ControlledWindow.__init__(self, *args, **kwargs)
        windowutils.UtilMixin.__init__(self)
        self.season = kwargs.get('season')
        self.parentList = kwargs.get('parentList')
        self.seasons = None
        if isinstance(self, AlbumWindow):
            self._show_ = kwargs.get('show')
        else:
            self.show_ = kwargs.get('show') or self.season.show()
        self.lastItem = None
        self.tasks = backgroundthread.Tasks()

    def onFirstInit(self):
        self.episodePanelControl = kodigui.ManagedControlList(self, self.EPISODE_PANEL_ID, 5)
        self.progressImageControl = self.getControl(self.PROGRESS_IMAGE_ID)

        self.setup()
        self.setFocusId(self.EPISODE_PANEL_ID)
        self.checkForHeaderFocus(xbmcgui.ACTION_MOVE_DOWN)

    def setup(self):
        self.updateProperties()
        self.fillEpisodes()

    def onAction(self, action):
        controlID = self.getFocusId()
        try:
            if action == xbmcgui.ACTION_LAST_PAGE and xbmc.getCondVisibility('ControlGroup(300).HasFocus(0)'):
                self.next()
            elif action == xbmcgui.ACTION_NEXT_ITEM:
                self.next()
            elif action == xbmcgui.ACTION_FIRST_PAGE and xbmc.getCondVisibility('ControlGroup(300).HasFocus(0)'):
                self.prev()
            elif action == xbmcgui.ACTION_PREV_ITEM:
                self.prev()

            if controlID == self.EPISODE_PANEL_ID:
                self.checkForHeaderFocus(action)
            if controlID == self.LIST_OPTIONS_BUTTON_ID and self.checkOptionsAction(action):
                return
            elif action == xbmcgui.ACTION_CONTEXT_MENU:
                if not xbmc.getCondVisibility('ControlGroup({0}).HasFocus(0)'.format(self.OPTIONS_GROUP_ID)):
                    self.setFocusId(self.OPTIONS_GROUP_ID)
                    return
            elif action in(xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_CONTEXT_MENU):
                if not xbmc.getCondVisibility('ControlGroup({0}).HasFocus(0)'.format(self.OPTIONS_GROUP_ID)):
                    self.setFocusId(self.OPTIONS_GROUP_ID)
                    return
        except:
            util.ERROR()

        kodigui.ControlledWindow.onAction(self, action)

    def checkOptionsAction(self, action):
        if action == xbmcgui.ACTION_MOVE_UP:
            mli = self.episodePanelControl.getSelectedItem()
            if not mli:
                return False
            pos = mli.pos() - 1
            if self.episodePanelControl.positionIsValid(pos):
                self.setFocusId(self.EPISODE_PANEL_ID)
                self.episodePanelControl.selectItem(pos)
            return True
        elif action == xbmcgui.ACTION_MOVE_DOWN:
            mli = self.episodePanelControl.getSelectedItem()
            if not mli:
                return False
            pos = mli.pos() + 1
            if self.episodePanelControl.positionIsValid(pos):
                self.setFocusId(self.EPISODE_PANEL_ID)
                self.episodePanelControl.selectItem(pos)
            return True

        return False

    def onClick(self, controlID):
        if controlID == self.HOME_BUTTON_ID:
            self.goHome()
        elif controlID == self.EPISODE_PANEL_ID:
            self.episodePanelClicked()
        elif controlID == self.PLAYER_STATUS_BUTTON_ID:
            self.show_AudioPlayer()
        elif controlID == self.PLAY_BUTTON_ID:
            self.playButtonClicked()
        elif controlID == self.SHUFFLE_BUTTON_ID:
            self.shuffleButtonClicked()
        elif controlID == self.OPTIONS_BUTTON_ID:
            self.optionsButtonClicked()
        elif controlID == self.SETTINGS_BUTTON_ID:
            self.settingsButtonClicked()
        elif controlID == self.INFO_BUTTON_ID:
            self.infoButtonClicked()
        elif controlID == self.SEARCH_BUTTON_ID:
            self.searchButtonClicked()

    def getSeasons(self):
        if not self.seasons:
            if self.season.TYPE == 'season':
                self.seasons = self.season.show().seasons()
            elif self.season.TYPE == 'album':
                self.seasons = self.season.artist().albums()

        if not self.seasons:
            return False

        return True

    def next(self):
        if not self._next():
            return
        self.setup()

    @busy.dialog()
    def _next(self):
        if self.parentList:
            mli = self.parentList.getListItemByDataSource(self.season)
            if not mli:
                return False

            pos = mli.pos() + 1
            if not self.parentList.positionIsValid(pos):
                pos = 0

            self.season = self.parentList.getListItem(pos).dataSource
        else:
            if not self.getSeasons():
                return False

            if self.season not in self.seasons:
                return False

            pos = self.seasons.index(self.season)
            pos += 1
            if pos >= len(self.seasons):
                pos = 0

            self.season = self.seasons[pos]

        return True

    def prev(self):
        if not self._prev():
            return
        self.setup()

    @busy.dialog()
    def _prev(self):
        if self.parentList:
            mli = self.parentList.getListItemByDataSource(self.season)
            if not mli:
                return False

            pos = mli.pos() - 1
            if pos < 0:
                pos = self.parentList.size() - 1

            self.season = self.parentList.getListItem(pos).dataSource
        else:
            if not self.getSeasons():
                return False

            if self.season not in self.seasons:
                return False

            pos = self.seasons.index(self.season)
            pos -= 1
            if pos < 0:
                pos = len(self.seasons) - 1

            self.season = self.seasons[pos]

        return True

    def searchButtonClicked(self):
        self.processCommand(search.dialog(self, section_id=self.season.getLibrarySectionId() or None))

    def playButtonClicked(self, shuffle=False):
        if shuffle:
            items = self.season.all()
            pl = playlist.LocalPlaylist(items, self.season.getServer())
            resume = False

            pl.shuffle(shuffle, first=True)
            videoplayer.play(play_queue=pl, resume=resume)
        else:
            self.episodePanelClicked()

    def shuffleButtonClicked(self):
        self.playButtonClicked(shuffle=True)

    def settingsButtonClicked(self):
        mli = self.episodePanelControl.getSelectedItem()
        if not mli:
            return

        episode = mli.dataSource

        if not episode.mediaChoice:
            playerObject = plexplayer.PlexPlayer(episode)
            playerObject.build()
        playersettings.showDialog(video=episode, non_playback=True)
        self.setItemAudioAndSubtitleInfo(episode, mli)

    def infoButtonClicked(self):
        mli = self.episodePanelControl.getSelectedItem()
        if not mli:
            return

        episode = mli.dataSource

        opener.handleOpen(
            info.InfoWindow,
            title=episode.title,
            sub_title='Season {0} Episode {1}'.format(episode.parentIndex, episode.index),
            thumb=episode.thumb,
            thumb_fallback='script.plex/thumb_fallbacks/episode.png',
            info=episode.summary,
            background=self.getProperty('background'),
            is_16x9=True
        )

    def episodePanelClicked(self, resume=False):
        mli = self.episodePanelControl.getSelectedItem()
        if not mli:
            return

        episode = mli.dataSource

        pl = playlist.LocalPlaylist(self.show_.all(), self.show_.getServer())
        if len(pl):  # Don't use playlist if it's only this video
            pl.setCurrent(episode)
            self.processCommand(videoplayer.play(play_queue=pl, resume=resume))
            return

    def optionsButtonClicked(self, from_item=False):
        options = []

        mli = self.episodePanelControl.getSelectedItem()

        if mli:
            if mli.dataSource.isWatched:
                options.append({'key': 'mark_unwatched', 'display': 'Mark Unwatched'})
            else:
                options.append({'key': 'mark_watched', 'display': 'Mark Watched'})

            # if True:
            #     options.append({'key': 'add_to_playlist', 'display': '[COLOR FF808080]Add To Playlist[/COLOR]'})

        if xbmc.getCondVisibility('Player.HasAudio + MusicPlayer.HasNext'):
            options.append({'key': 'play_next', 'display': 'Play Next'})

        if not isinstance(self, AlbumWindow):
            if self.season.isWatched:
                options.append({'key': 'mark_season_unwatched', 'display': 'Mark Season Unwatched'})
            else:
                options.append({'key': 'mark_season_watched', 'display': 'Mark Season Watched'})

        # if xbmc.getCondVisibility('Player.HasAudio') and self.section.TYPE == 'artist':
        #     options.append({'key': 'add_to_queue', 'display': 'Add To Queue'})

        if options:
            options.append(dropdown.SEPARATOR)

        options.append({'key': 'to_show', 'display': isinstance(self, AlbumWindow) and 'Go to Artist' or 'Go To Show'})
        options.append({'key': 'to_section', 'display': u'Go to {0}'.format(self.season.getLibrarySectionTitle())})

        pos = (460, 685)
        bottom = False
        setDropdownProp = False
        if from_item:
            viewPos = self.episodePanelControl.getViewPosition()
            if viewPos > 6:
                pos = (1490, 312 + (viewPos * 100))
                bottom = True
            else:
                pos = (1490, 167 + (viewPos * 100))
                bottom = False
            setDropdownProp = True
        choice = dropdown.showDropdown(options, pos, pos_is_bottom=bottom, close_direction='right', set_dropdown_prop=setDropdownProp)
        if not choice:
            return

        if choice['key'] == 'play_next':
            xbmc.executebuiltin('PlayerControl(Next)')
        elif choice['key'] == 'mark_watched':
            media = mli.dataSource
            media.markWatched()
            self.updateItems(mli)
            util.MONITOR.watchStatusChanged()
        elif choice['key'] == 'mark_unwatched':
            media = mli.dataSource
            media.markUnwatched()
            self.updateItems(mli)
            util.MONITOR.watchStatusChanged()
        elif choice['key'] == 'mark_season_watched':
            media = self.season
            media.markWatched()
            util.MONITOR.watchStatusChanged()
        elif choice['key'] == 'mark_season_unwatched':
            media = self.season
            media.markUnwatched()
            util.MONITOR.watchStatusChanged()
        elif choice['key'] == 'to_show':
            self.processCommand(opener.open(self.season.parentRatingKey))
        elif choice['key'] == 'to_section':
            self.goHome(self.season.getLibrarySectionId())

    def checkForHeaderFocus(self, action):
        mli = self.episodePanelControl.getSelectedItem()
        if not mli:
            return

        if mli != self.lastItem:
            self.lastItem = mli
            self.setProgress(mli)

        if action in (xbmcgui.ACTION_MOVE_UP, xbmcgui.ACTION_PAGE_UP):
            if mli.getProperty('is.header'):
                xbmc.executebuiltin('Action(up)')
        if action in (xbmcgui.ACTION_MOVE_DOWN, xbmcgui.ACTION_PAGE_DOWN, xbmcgui.ACTION_MOVE_LEFT, xbmcgui.ACTION_MOVE_RIGHT):
            if mli.getProperty('is.header'):
                xbmc.executebuiltin('Action(down)')

    def updateProperties(self):
        self.setProperty(
            'background',
            (self.show_ or self.season.show()).art.asTranscodedImageURL(self.width, self.height, blur=128, opacity=60, background=colors.noAlpha.Background)
        )
        self.setProperty('season.thumb', self.season.thumb.asTranscodedImageURL(*self.POSTER_DIM))
        self.setProperty('show.title', self.show_ and self.show_.title or '')
        self.setProperty('season.title', self.season.title)

    def createListItem(self, obj):
        mli = kodigui.ManagedListItem(
            obj.title, obj.originallyAvailableAt.asDatetime('%b %d, %Y'), thumbnailImage=obj.thumb.asTranscodedImageURL(*self.THUMB_AR16X9_DIM), data_source=obj
        )
        mli.setProperty('episode.number', str(obj.index) or '')
        mli.setProperty('episode.duration', util.durationToText(obj.duration.asInt()))
        mli.setProperty('unwatched', not obj.isWatched and '1' or '')
        # mli.setProperty('progress', util.getProgressImage(obj))
        return mli

    def updateItems(self, item=None):
        if item:
            self.season.reload()
            item.setProperty('watched', item.dataSource.isWatched and '1' or '')
        else:
            self.fillEpisodes(update=True)

    def setItemInfo(self, video, mli):
        # video.reload(checkFiles=1)
        mli.setProperty('background', video.art.asTranscodedImageURL(self.width, self.height, blur=128, opacity=60, background=colors.noAlpha.Background))
        mli.setProperty('title', video.title)
        mli.setProperty('show.title', video.grandparentTitle or (self.show_.title if self.show_ else ''))
        mli.setProperty('duration', util.durationToText(video.duration.asInt()))
        mli.setProperty('summary', video.summary.strip().replace('\t', ' '))

        mli.setProperty('season', 'Season {0}'.format(video.parentIndex))
        mli.setProperty('episode', 'Episode {0}'.format(video.index))
        mli.setProperty('date', util.cleanLeadingZeros(video.originallyAvailableAt.asDatetime('%B %d, %Y')))

        # mli.setProperty('related.header', 'Related Shows')
        mli.setProperty('year', video.year)
        mli.setProperty('content.rating', video.contentRating.split('/', 1)[-1])
        genres = self.show_.genres()[0].tag  # u' / '.join([g.tag for g in self.video.genres()][:3])
        mli.setProperty('genre', genres)

        if video.get('userRating'):
            stars = str(int(round((video.userRating.asFloat() / 10) * 5)))
            mli.setProperty('rating.stars', stars)
        # elif video.rating:
        #     stars = str(int(round((video.rating.asFloat() / 10) * 5)))
        #     mli.setProperty('rating.stars', stars)

        if video.get('ratingImage'):
            rating = video.rating
            audienceRating = video.audienceRating
            if video.ratingImage.startswith('rottentomatoes:'):
                rating = '{0}%'.format(int(rating.asFloat() * 10))
                if audienceRating:
                    audienceRating = '{0}%'.format(int(audienceRating.asFloat() * 10))

            mli.setProperty('rating', rating)
            mli.setProperty('rating.image', 'script.plex/ratings/{0}.png'.format(video.ratingImage.replace('://', '/')))
            if video.get('audienceRatingImage'):
                mli.setProperty('rating2', audienceRating)
                mli.setProperty('rating2.image', 'script.plex/ratings/{0}.png'.format(video.audienceRatingImage.replace('://', '/')))
        else:
            mli.setProperty('rating', video.rating)

    def setPostReloadItemInfo(self, video, mli):
        self.setItemAudioAndSubtitleInfo(video, mli)

        mli.setProperty('video.res', video.resolutionString())
        mli.setProperty('audio.codec', video.audioCodecString())
        mli.setProperty('audio.channels', video.audioChannelsString())
        mli.setBoolProperty('unavailable', not video.media()[0].isAccessible())

    def setItemAudioAndSubtitleInfo(self, video, mli):
        sas = video.selectedAudioStream()
        mli.setProperty('audio', sas and sas.getTitle() or 'None')

        sss = video.selectedSubtitleStream()
        if sss:
            if len(video.subtitleStreams) > 1:
                mli.setProperty('subtitles', u'{0} \u2022 {1} More'.format(sss.getTitle(), len(video.subtitleStreams) - 1))
            else:
                mli.setProperty('subtitles', sss.getTitle())
        else:
            if video.subtitleStreams:
                mli.setProperty('subtitles', u'None \u2022 {0} Available'.format(len(video.subtitleStreams)))
            else:
                mli.setProperty('subtitles', u'None')

    def setProgress(self, mli):
        video = mli.dataSource

        if video.viewOffset.asInt():
            width = video.viewOffset.asInt() and (1 + int((video.viewOffset.asInt() / video.duration.asFloat()) * self.width)) or 1
            self.progressImageControl.setWidth(width)
        else:
            self.progressImageControl.setWidth(1)

    @busy.dialog()
    def fillEpisodes(self, update=False):
        items = []
        idx = 0
        for episode in self.season.episodes():
            mli = self.createListItem(episode)
            self.setItemInfo(episode, mli)
            if mli:
                mli.setProperty('index', str(idx))
                items.append(mli)
                idx += 1

        self.episodePanelControl.replaceItems(items)

        self.reloadItems(items)

    def reloadItems(self, items):
        tasks = []
        for mli in items:
            task = EpisodeReloadTask().setup(mli.dataSource, self.reloadItemCallback)
            self.tasks.add(task)
            tasks.append(task)

        backgroundthread.BGThreader.addTasks(tasks)

    def reloadItemCallback(self, episode):
        for mli in self.episodePanelControl:
            if mli.dataSource == episode:
                self.setPostReloadItemInfo(episode, mli)
                return


class AlbumWindow(EpisodesWindow):
    xmlFile = 'script-plex-album.xml'

    def playButtonClicked(self, shuffle=False):
        pl = playlist.LocalPlaylist(self.season.all(), self.season.getServer())
        pl.startShuffled = shuffle
        self.openWindow(musicplayer.MusicPlayerWindow, track=pl.current(), playlist=pl)

    def episodePanelClicked(self):
        mli = self.episodePanelControl.getSelectedItem()
        if not mli:
            return

        self.openWindow(musicplayer.MusicPlayerWindow, track=mli.dataSource, album=self.season)

    def updateProperties(self):
        self.setProperty(
            'background',
            self.season.art.asTranscodedImageURL(self.width, self.height, blur=128, opacity=60, background=colors.noAlpha.Background)
        )
        self.setProperty('season.thumb', self.season.thumb.asTranscodedImageURL(*self.POSTER_DIM))
        self.setProperty('artist.title', self.season.parentTitle or '')
        self.setProperty('album.title', self.season.title)

    def createListItem(self, obj):
        mli = kodigui.ManagedListItem(obj.title, data_source=obj)
        mli.setProperty('track.number', str(obj.index) or '')
        mli.setProperty('track.duration', util.simplifiedTimeDisplay(obj.duration.asInt()))
        return mli

    @busy.dialog()
    def fillEpisodes(self):
        items = []
        idx = 0
        multiDisc = 0

        for track in self.season.tracks():
            disc = track.parentIndex.asInt()
            if disc > 1:
                if not multiDisc:
                    items.insert(0, kodigui.ManagedListItem('DISC 1', properties={'is.header': '1'}))

                if disc != multiDisc:
                    items[-1].setProperty('is.footer', '1')
                    multiDisc = disc
                    items.append(kodigui.ManagedListItem('DISC {0}'.format(disc), properties={'is.header': '1'}))

            mli = self.createListItem(track)
            if mli:
                mli.setProperty('track.ID', track.ratingKey)
                mli.setProperty('index', str(idx))
                mli.setProperty('artist', self.season.parentTitle)
                mli.setProperty('disc', str(disc))
                mli.setProperty('album', self.season.title)
                mli.setProperty('number', '{0:0>2}'.format(track.index))
                items.append(mli)
                idx += 1

        if items:
            items[-1].setProperty('is.footer', '1')

        self.episodePanelControl.replaceItems(items)
