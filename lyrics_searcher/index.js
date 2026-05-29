// Code from https://github.com/NTag/lyrics.ovh

const express = require("express");
const cheerio = require('cheerio');
const request = require("request-promise");
const cors = require("cors");
const _ = require('lodash');

let appApi = express();
const portApi = 8080;

appApi.use(cors());

appApi.get("/v1/:artist/:title", function (req, res) {
  if (!req.params.artist || !req.params.title) {
    return res.status(400).send({ error: "Artist or title missing" });
  }
    findLyrics(req.params.title, req.params.artist)
    .then((l) => {
      res.send({ lyrics: l });
    })
    .catch((e) => {
      // console.log(e);
      res.status(404).send({ error: "No lyrics found" });
    });
});

appApi.get("/suggest/:term", function (req, res) {
  request({
    uri: "http://api.deezer.com/search?limit=15&q=" + req.params.term,
    json: true,
  }).then((results) => {
    res.send(results);
  });
});

appApi.listen(portApi, function () {
  console.log("API listening on port " + portApi);
});


// code from alltomp3

findLyrics = (title, artistName) => {
  let promises = [];

  const textln = (html) => {
    html.find('br').replaceWith('\n');
    html.find('script').replaceWith('');
    html.find('#video-musictory').replaceWith('');
    html.find('strong').replaceWith('');
    html = _.trim(html.text());
    html = html.replace(/\r\n\n/g, '\n');
    html = html.replace(/\t/g, '');
    html = html.replace(/\n\r\n/g, '\n');
    html = html.replace(/ +/g, ' ');
    html = html.replace(/\n /g, '\n');
    return html;
  };

  const lyricsUrl = (title) => {
    return _.kebabCase(_.trim(_.toLower(_.deburr(title))));
  };
  const lyricsManiaUrl = (title) => {
    return _.snakeCase(_.trim(_.toLower(_.deburr(title))));
  };
  const lyricsManiaUrlAlt = (title) => {
    title = _.trim(_.toLower(title));
    title = title.replace("'", '');
    title = title.replace(' ', '_');
    title = title.replace(/_+/g, '_');
    return title;
  };

  const reqWikia = request({
    uri: 'http://lyrics.wikia.com/wiki/' + encodeURIComponent(artistName) + ':' + encodeURIComponent(title),
    transform: (body) => {
      return cheerio.load(body);
    },
  }).then(($) => {
    return textln($('.lyricbox'));
  });

  const reqParolesNet = request({
    uri: 'http://www.paroles.net/' + lyricsUrl(artistName) + '/paroles-' + lyricsUrl(title),
    transform: (body) => {
      return cheerio.load(body);
    },
  }).then(($) => {
    if ($('.song-text').length === 0) {
      return Promise.reject();
    }
    return textln($('.song-text'));
  });

  const reqLyricsMania1 = request({
    uri: 'http://www.lyricsmania.com/' + lyricsManiaUrl(title) + '_lyrics_' + lyricsManiaUrl(artistName) + '.html',
    transform: (body) => {
      return cheerio.load(body);
    },
  }).then(($) => {
    if ($('.lyrics-body').length === 0) {
      return Promise.reject();
    }
    return textln($('.lyrics-body'));
  });

  const reqLyricsMania2 = request({
    uri: 'http://www.lyricsmania.com/' + lyricsManiaUrl(title) + '_' + lyricsManiaUrl(artistName) + '.html',
    transform: (body) => {
      return cheerio.load(body);
    },
  }).then(($) => {
    if ($('.lyrics-body').length === 0) {
      return Promise.reject();
    }
    return textln($('.lyrics-body'));
  });

  const reqLyricsMania3 = request({
    uri:
      'http://www.lyricsmania.com/' +
      lyricsManiaUrlAlt(title) +
      '_lyrics_' +
      encodeURIComponent(lyricsManiaUrlAlt(artistName)) +
      '.html',
    transform: (body) => {
      return cheerio.load(body);
    },
  }).then(($) => {
    if ($('.lyrics-body').length === 0) {
      return Promise.reject();
    }
    return textln($('.lyrics-body'));
  });

  const reqSweetLyrics = request({
    method: 'POST',
    uri: 'http://www.sweetslyrics.com/search.php',
    form: {
      search: 'title',
      searchtext: title,
    },
    transform: (body) => {
      return cheerio.load(body);
    },
  })
    .then(($) => {
      let closestLink,
        closestScore = -1;
      _.forEach($('.search_results_row_color'), (e) => {
        let artist = $(e)
          .text()
          .replace(/ - .+$/, '');
        let currentScore = levenshtein.get(artistName, artist);
        if (closestScore === -1 || currentScore < closestScore) {
          closestScore = currentScore;
          closestLink = $(e).find('a').last().attr('href');
        }
      });
      if (!closestLink) {
        return Promise.reject();
      }
      return request({
        uri: 'http://www.sweetslyrics.com/' + closestLink,
        transform: (body) => {
          return cheerio.load(body);
        },
      });
    })
    .then(($) => {
      return textln($('.lyric_full_text'));
    });

  if (/\(.*\)/.test(title) || /\[.*\]/.test(title)) {
    promises.push(at3.findLyrics(title.replace(/\(.*\)/g, '').replace(/\[.*\]/g, ''), artistName));
  }

  promises.push(reqWikia);
  promises.push(reqParolesNet);
  promises.push(reqLyricsMania1);
  promises.push(reqLyricsMania2);
  promises.push(reqLyricsMania3);
  promises.push(reqSweetLyrics);

  return Promise.any(promises).then((lyrics) => {
    return lyrics;
  });
};
