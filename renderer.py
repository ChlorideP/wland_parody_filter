# -*- encoding: utf-8 -*-
# @File   : renderer.py
# @Time   : 2023/08/27 10:38:32
# @Author : Chloride

from abc import ABCMeta, abstractmethod
from typing import Optional

import aiofiles
from aiofiles.threadpool.text import AsyncTextIOWrapper

from wland import WlandPassage

AUTHOR = "Author"
TITLE = "Title"
ORIGINS = "Origins"
TAGS = "Tags"


class SheetGenerator(metaclass=ABCMeta):
    """Base class of Filter Result generator.

    File stream needs manual management."""
    def __init__(self, filename, encoding='utf-8'):
        self.fn = filename
        self.enc = encoding
        self.__stream: Optional[AsyncTextIOWrapper] = None

    @property
    def stream(self):
        return self.__stream  # shouldn't access directly.

    @abstractmethod
    def tableItem(self, p: WlandPassage):
        pass

    @property
    @abstractmethod
    def table(self):
        pass

    async def open(self):
        try:
            self.__stream = await aiofiles.open(
                self.fn, 'w', encoding=self.enc)
            return await self.__stream.writable()
        except Exception:
            await self.close()
            return False

    async def close(self):
        await self.__stream.close()
        self.__stream = None

    async def append(self, p: WlandPassage):
        await self.__stream.write(f"{self.tableItem(p)}\n")


class CSV(SheetGenerator):
    def __init__(self, filename):
        super().__init__(filename, 'utf-8-sig')

    @property
    def table(self):
        return ','.join([f'{AUTHOR} UID', f'{AUTHOR} user name',
                         'WID', TITLE, ORIGINS, TAGS])

    def tableItem(self, p: WlandPassage):
        return "%s,%s,%s,%s,%s,%s" % (
            p.author_uid, p.author_name, p.wid, p.title,
            " ".join(p.hashtags), " ".join(p.tags))

    async def open(self):
        if not await super().open():
            return
        await self.stream.write(f"{self.table}\n")


class MarkDown(SheetGenerator):
    def __init__(self, filename, domain):
        super().__init__(filename)
        self.wland_domain = domain

    @staticmethod
    def _table_item(*elems):
        ret = ""
        for i in elems:
            ret += f"|{i}"
        ret += "|"
        return ret

    @property
    def table(self):
        return "%s\n%s\n" % (
            self._table_item(AUTHOR, TITLE, ORIGINS, TAGS),
            self._table_item('-', '-', '-', '-'))

    def tableItem(self, p: WlandPassage):
        return self._table_item(
            self.link(p.author_name,
                      f"https://{self.wland_domain}/u{p.author_uid}"),
            self.link(p.title,
                      f"https://{self.wland_domain}/wid{p.wid}"),
            ", ".join(p.hashtags),
            ", ".join(p.tags))

    def link(self, str_shown, str_link):
        return "[%s](%s)" % (str_shown, str_link)

    async def open(self):
        if not await super().open():
            return
        await self.stream.write(self.table)


class HTML(SheetGenerator):
    def __init__(self, filename, domain):
        super().__init__(filename)
        self.wland_domain = domain

    @staticmethod
    def label(item: str, end=True, **properties):
        """generate HTML label.

        The string looks like: `<item pKey="pVal">{0}</item>`,
        or when `end` is False, `<item pKey="pVal"/>{0}`.

        Consider using `str.format()` to send argument."""
        ret = f"<{item}"
        for k, v in properties.items():
            ret += f' {k}="{v}"'
        ret += ">{0}</%s>" % item if end else "/>{0}"
        return ret

    def _table_item(self, *elems, header=False):
        return self.label('tr').format(''.join([self.label(
            'th' if header else 'td', False).format(i) for i in elems]))

    @property
    def head(self):
        return self.label('head').format("%s%s" % (
            self.label('meta', False, charset='utf-8')
                .format('').replace('/>', '>'),
            self.label('title').format('Wland Parody Filter')))

    def link(self, str_shown, str_link):
        return self.label(
            'a', href=str_link, target='_blank', rel='noopener noreferrer'
            ).format(str_shown)

    @property
    def table(self):
        return self.label('table', border=1).format('%s%s' % (
            self.label('caption', False).format('Search Result'),
            self._table_item(AUTHOR, TITLE, ORIGINS, TAGS, header=True)))

    def tableItem(self, p: WlandPassage):
        return self._table_item(
            self.link(p.author_name,
                      f'https://{self.wland_domain}/u{p.author_uid}'),
            self.link(p.title,
                      f'https://{self.wland_domain}/wid{p.wid}'),
            ", ".join(p.hashtags),
            ", ".join(p.tags))

    async def open(self):
        if not await super().open():
            return
        await self.stream.write(f'<html>{self.head}\n')
        await self.stream.write('<body>%s\n' % (
            self.table.replace("</table>", "")))

    async def close(self):
        if await self.stream.writable():
            await self.stream.write('</table></body></html>\n')
        return await super().close()


def initSheet(ft: str, url) -> SheetGenerator:
    ft = f'./wland.{ft.lower()}'
    if ft.endswith(('html', 'htm'),):
        return HTML(ft, url)
    elif ft.endswith('md'):
        return MarkDown(ft, url)
    else:
        return CSV(ft)
