#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

class MenuItem():
    def __init__(self, label:str, submenu:list=None, function:callable=None) -> None:
        self.label = label
        self.submenu = submenu
        self.function = function

class Menu():
    def __init__(self, hierarchy:list):
        #self.hierarchy = hierarchy
        self.contents = list()
        self.orders = list()
        if hierarchy:
            self.contents.append(hierarchy)
            self.orders.append(0)

    def back(self):
        if not self.contents or len(self.contents) == 1:
            return

        self.contents = self.contents[:-1]
        self.orders = self.orders[:-1]

    def enter(self):
        if not self.contents:
            return

        item:MenuItem = self.contents[-1][self.orders[-1]]

        if item.function:
            item.function(menu_item=item)

        if item.submenu:
            self.contents.append(item.submenu)
            self.orders.append(0)


    def down(self):
        if not self.contents:
            return
        if self.orders[-1] + 1  <  len(self.contents[-1]):
            self.orders[-1] += 1

    def up(self):
        if not self.orders:
            return
        if  self.orders[-1] > 0:
            self.orders[-1] -= 1

    def get_current_order(self):
        if not self.orders:
            return 0
        return self.orders[-1]

    def get_current_items(self):
        if not self.contents:
            return 0
        return self.contents[-1]
