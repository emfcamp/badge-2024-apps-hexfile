import os
import asyncio
from shutil import rmtree
from app import App
from app_components import Menu, Notification, TextDialog, clear_background
from firmware_apps.intro_app import Hexagon

def path_isdir(path):
    try:
        return (os.stat(path)[0] & 0x4000) != 0
    except OSError:
        return False

class Hexfile(App):
    def __init__(self):
        self.notification = None
        self.overlays = []
        self.choices = None
        self.clipboard = None
        self.dialog = None
        self.menu = None
        self.create_dir_wait = False
        self.rename_wait = False
        self.hexagons = [Hexagon() for _ in range(5)]
        self.time_elapsed = 0
        os.chdir('/')
        self.list_folder()

    def list_folder(self):
        self.path_contents = os.listdir()
        self.path_contents.insert(0,'select folder')
        if os.getcwd() is not '/':
            self.path_contents.insert(0,'..')
        self.menu = Menu(
            self,
            self.path_contents,
            select_handler=self.select_handler,
            back_handler=self.back_handler,
        )
        self.menu.position = 0

    async def run(self, render_update):
        while True:
            await render_update()
            await asyncio.sleep(0.1)
            self.update(100)
            if self.dialog:
                if self.create_dir_wait:
                    result = await self.dialog.run(render_update)
                    if result is not False and result is not '':
                        self.create_dir(self.path + result)
                    self.create_dir_wait = False
                if self.rename_wait:
                    result = await self.dialog.run(render_update)
                    if result is not False and result is not '':
                        os.rename(self.path, self.path[:self.path.rfind('/') +1] + result)
                        self.notification = Notification('Renamed')
                    self.rename_wait = False
                self.dialog = None
                os.chdir('/')
                self.list_folder()
    
    def select_handler(self, item, idx):
        if item in self.path_contents:
            self.menu._cleanup()
            if item is '..':
                os.chdir(os.getcwd()[0:1 if os.getcwd().rfind('/') is 0 else os.getcwd().rfind('/')])
                self.list_folder()
            elif item is not 'select folder' and path_isdir(os.getcwd().rstrip('/') + '/' + item ):
                os.chdir(os.getcwd().rstrip('/') + '/' + item)
                self.list_folder()
            else:
                if os.getcwd() is '/':
                    self.choices = []
                else:
                    self.choices = ['Copy', 'Cut', 'Delete', 'Cancel']
                if item is not 'select folder':
                    self.path = os.getcwd().rstrip('/') + '/' + item
                    self.choices.append('Rename')
                else:
                    if item is 'select folder':
                        self.choices.append('mkdir')
                    self.path = os.getcwd().rstrip('/') + '/'
                    if self.clipboard is not None:
                        if self.path.rstrip() != self.clipboard[0].rstrip():
                            self.choices.insert(0, 'Paste')
                self.menu = Menu(
                    self,
                    self.choices,
                    select_handler=self.choice_handler,
                    back_handler=self.back_handler,
                )
                self.menu.position = 0
        else:
            self.notification = Notification('Unknown selection: "' + item + '"!')

    def back_handler(self):
        if os.getcwd() is '/':
            self.minimise()
        else:
            self.select_handler('..', 0)

    def choice_handler(self, item, idx):
        self.menu._cleanup()
        self.menu = None
        if item is 'Copy' or item is 'Cut':
            self.clipboard = ( self.path, item )
        elif item is 'Paste':
            if self.path[-6:] is 'app.py' or self.path[-7:] is 'app.mpy' and os.getcwd() is '/':
                self.notification = Notification('Not Allowed')
            else: 
                if path_isdir(self.clipboard[0] + '/'):
                    self.copytree(self.clipboard[0], self.path)
                else:
                    self.copy(self.clipboard[0], self.path)
                if self.clipboard[1] is 'Cut':
                    self.delete(self.clipboard[0])
                    self.notification = Notification('Cut')
                else:
                    self.notification = Notification('Copied')
            self.clipboard = None
        elif item is 'Delete':
            self.delete(self.path)
            self.clipboard = None
        elif item is 'mkdir':
            self.dialog = TextDialog('mkdir', self) 
            self.create_dir_wait = True
        elif item is 'Rename':
            self.dialog = TextDialog('rename', self) 
            self.rename_wait = True
        elif item is not 'Cancel':
            os.chdir('/')
            self.notification = Notification('Unknown Choice')            
        if not self.create_dir_wait and not self.rename_wait:
            self.list_folder()
        
    def draw(self, ctx):
        ctx.save()
        clear_background(ctx)
        for hexagon in self.hexagons:
            hexagon.draw(ctx)
        if self.menu:
            self.menu.draw(ctx)
        if self.dialog:        
            self.dialog.draw(ctx)
        if self.notification:
            self.notification.draw(ctx)
        ctx.restore()

    def update(self, delta):
        if self.menu:
            self.menu.update(delta)
        if self.notification:
            self.notification.update(delta)
        self.time_elapsed += delta / 1_000
        for hexagon in self.hexagons:
            hexagon.update(self.time_elapsed)
            
    def create_dir(self, directory):
        try:
            os.stat(directory)
            self.notification = Notification('Dir Exists')
        except OSError:
            os.mkdir(directory)
            self.notification = Notification('Dir Created')
            
    def copy( self, source, destination):
        try:
            os.stat(source)
            try:
                if path_isdir(destination):
                    destination = destination.rstrip('/') + '/' + source[source.rfind('/')+1:]
                else:
                    #it already exists so delete it before copying.
                    self.delete(destination)
            except OSError:
                pass
            try:
                with open(source, "rb") as s:
                    with open(destination, "wb") as d:
                        while True:
                            l = s.read(512)
                            if not l: break
                            d.write(l)
                print('file ' + source + ' copied to ' + destination )
            except OSError as e:
                self.notification = Notification('copy fail: ' + str(e))
        except OSError as e:
            self.notification = Notification('os.stat ' + str(e))

    def copytree(self, source, destination):
        folder = source[source.rstrip('/').rfind('/') + 1:-1]
        self.create_dir(destination + folder)
        for file in os.listdir(source):
            if path_isdir(source + file + '/'):
                self.create_dir(destination + folder + '/' + file)
                for subfile in os.listdir(source + file):
                    if path_isdir(source + file + '/' + subfile + '/'):
                        self.create_dir(destination + folder + '/' + file + '/' + subfile)
                        for subsubfile in os.listdir(source + file + '/' + subfile):
                            if path_isdir(source + file + '/' + subfile + '/' + subsubfile + '/'):
                                # not using recursion, so need to stop somewhere
                                self.notification = Notification('Too deep')
                            else:
                                self.copy(source + file + '/' + subfile + '/' + subsubfile, destination + folder + '/' + file + '/' + subfile)
                    else:
                        self.copy(source + file + '/' + subfile, destination + folder + '/' + file)
            else:
                self.copy(source + file, destination + folder)
                
    def delete( self, file ):
        try:
            if path_isdir(file):
                os.chdir(os.getcwd()[0:1 if os.getcwd().rfind('/') is 0 else os.getcwd().rfind('/')])
                rmtree(file)
            else:
                os.remove(file)
            self.notification = Notification('Deleted')
        except OSError as e:
            self.notification = Notification('Delete failed' + str(e))

__app_export__ = Hexfile