"""Minimum Overpass API interface"""
import re

import download

API_URL = "http://overpass-api.de/api/interpreter?"
#API_URL = "http://overpass.osm.rambler.ru/cgi/interpreter?"


class Query(object):
    """Class for a query to Overpass"""

    def __init__(self, search_area, output='xml', down=True, meta=True):
        """
        Args:
            search_area (str): See set_search_area
            output (str): xml (default) / json
            down (bool): True (default) to include recurse down elements
            meta (bool): True (default) to include metadata
        """
        self.output = output
        self.down = '(._;>;);' if down else ''
        self.meta = 'out meta;' if meta else 'out;'
        self.area_id = ''
        self.bbox = ''
        self.set_search_area(search_area)
        self.statements = []
        self.url = ''

    def set_search_area(self, search_area):
        """Set the area to search in. It could either the osm id of a named area
           or a bounding box (bottom, left, top, right) clause."""
        if re.match('^\d{1,8}$', search_area):
            self.area_id = search_area
            self.bbox = ''
        elif re.match('^(-?\d{1,3}(\.\d+)?,\s*){3}-?\d{1,3}(\.\d+)?$', search_area):
            self.bbox = search_area
            self.area_id = ''
        else:
            raise TypeError("Argument expected to be an area id or a bbox "
                            "clause: %s" % search_area)

    def add(self, *args):
        """Adds a statement to the query. Use QL query statements without bbox
           or area clauses. Example: node["name"="Berlin"]"""
        rsc = lambda s: s[:-1] if s[-1] == ';' else s
        for arg in args:
            if hasattr(arg, '__iter__'):
                self.statements += [rsc(s) for s in arg]
            else:
                self.statements += rsc(arg).split(';')
        return self
    
    def get_url(self):
        """Returns url for the query"""
        if len(self.statements) > 0:
            ql = '({s});'.join(self.statements) + '({s});'
            if self.area_id:
                query = 'area(36{id:>08})->.searchArea;' + ql
                query = query.format(id=self.area_id, s='area.searchArea')
            else:
                query = ql.format(s=self.bbox)
            self.url = '{u}data=[out:{o}];({q});{d}{m}'.format(u=API_URL, 
                q=query, o=self.output, d=self.down, m=self.meta)
        return self.url

    def download(self, filename):
        """Downloads query result to filename"""
        download.wget(self.get_url(), filename)
    
    def read(self):
        """Returns query result"""
        response = download.get_response(self.get_url())
        return response.text
