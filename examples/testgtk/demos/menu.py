#!/usr/bin/env python
'''Menus Test

This example demonstrates the use of various menu types in gtk.  It
demonstrates the new submenu navigation and scrolling menu features of
gtk 2.0.'''

description = 'Menus'

import gtk

def create_menu(depth, length=5):
    if depth < 1:
	return None
    menu = gtk.GtkMenu()
    group= None
    for i in range(length):
	menuitem = gtk.GtkRadioMenuItem(group, 'item %2d - %d' % (depth, i))
	group = menuitem
	menu.add(menuitem)
	menuitem.show()
	if depth > 1:
	    submenu = create_menu(depth - 1)
	    menuitem.set_submenu(submenu)
    return menu

def main():
    window = gtk.GtkWindow()
    if __name__ == '__main__':
	window.connect('destroy', lambda win: gtk.main_quit())
    window.set_title('Menus')

    vbox = gtk.GtkVBox()
    window.add(vbox)

    menubar = gtk.GtkMenuBar()
    vbox.pack_start(menubar, expand=gtk.FALSE)

    menuitem = gtk.GtkMenuItem('test\nline2')
    menuitem.set_submenu(create_menu(2, 50))
    menubar.add(menuitem)

    menuitem = gtk.GtkMenuItem('foo')
    menuitem.set_submenu(create_menu(2))
    menubar.add(menuitem)
    
    menuitem = gtk.GtkMenuItem('bar')
    menuitem.set_submenu(create_menu(2))
    menuitem.right_justify()
    menubar.add(menuitem)

    vbox2 = gtk.GtkVBox(spacing=10)
    vbox2.set_border_width(10)
    vbox.pack_start(vbox2)

    optionmenu = gtk.GtkOptionMenu()
    optionmenu.set_menu(create_menu(1,50))
    vbox2.pack_start(optionmenu)

    separator = gtk.GtkHSeparator()
    vbox.pack_start(separator, expand=gtk.FALSE)
    
    vbox2 = gtk.GtkVBox(spacing=10)
    vbox2.set_border_width(10)
    vbox.pack_start(vbox2, expand=gtk.FALSE)

    button = gtk.GtkButton('close')
    button.connect('destroy', lambda widget, window=window: window.destroy())
    vbox2.pack_start(button)
    button.set_flags(gtk.CAN_DEFAULT)
    button.grab_default()

    window.show_all()

    if __name__ == '__main__': gtk.main()
if __name__ == '__main__': main()
