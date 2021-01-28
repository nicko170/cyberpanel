#!/usr/local/CyberCP/bin/python
import threading as multi
from plogical.CyberCPLogFileWriter import CyberCPLogFileWriter as logging
from plogical.virtualHostUtilities import virtualHostUtilities
from plogical.processUtilities import ProcessUtilities
from .models import Websites, ChildDomains
from plogical.applicationInstaller import ApplicationInstaller
from plogical.mysqlUtilities import mysqlUtilities
from random import randint
import os


class StagingSetup(multi.Thread):

    def __init__(self, function, extraArgs):
        multi.Thread.__init__(self)
        self.function = function
        self.extraArgs = extraArgs

    def run(self):
        try:
            if self.function == 'startCloning':
                self.startCloning()
            elif self.function == 'startSyncing':
                self.startSyncing()
        except BaseException as msg:
            logging.writeToFile(str(msg) + ' [StagingSetup.run]')

    def startCloning(self):
        try:
            tempStatusPath = self.extraArgs['tempStatusPath']
            self.tempStatusPath = tempStatusPath
            masterDomain = self.extraArgs['masterDomain']
            domain = self.extraArgs['domain']
            admin = self.extraArgs['admin']

            website = Websites.objects.get(domain=masterDomain)

            masterPath = '/home/%s/public_html' % (masterDomain)
            configPath = '%s/wp-config.php' % (masterPath)

            ## Check if WP Detected on Main Site

            command = 'ls -la %s' % (configPath)
            output = ProcessUtilities.outputExecutioner(command)

            if output.find('No such file or') > -1:
                logging.statusWriter(tempStatusPath, 'WordPress is not detected. [404]')
                return 0

            ##

            command = 'chmod 755 %s' % (masterPath)
            ProcessUtilities.executioner(command)

            ## Creating Child Domain

            path = "/home/" + masterDomain + "/" + domain

            logging.statusWriter(tempStatusPath, 'Creating domain for staging environment..,5')
            phpSelection = website.phpSelection
            execPath = "/usr/local/CyberCP/bin/python " + virtualHostUtilities.cyberPanel + "/plogical/virtualHostUtilities.py"

            execPath = execPath + " createDomain --masterDomain " + masterDomain + " --virtualHostName " + domain + \
                       " --phpVersion '" + phpSelection + "' --ssl 1 --dkimCheck 0 --openBasedir 0 --path " + path + ' --websiteOwner ' \
                       + admin.userName + ' --tempStatusPath  %s' % (tempStatusPath + '1') + " --apache 0"

            ProcessUtilities.executioner(execPath)

            domainCreationStatusPath = tempStatusPath + '1'

            data = open(domainCreationStatusPath, 'r').read()

            if data.find('[200]') > -1:
                pass
            else:
                logging.statusWriter(tempStatusPath, 'Failed to create child-domain for staging environment. [404]')
                return 0

            logging.statusWriter(tempStatusPath, 'Domain successfully created..,15')

            ## Creating WP Site and setting Database

            command = 'wp core download --path=%s' % (path)
            ProcessUtilities.executioner(command, website.externalApp)

            logging.statusWriter(tempStatusPath, 'Creating and copying database..,50')

            dbNameRestore, dbUser, dbPassword = ApplicationInstaller(None, None).dbCreation(tempStatusPath, website)

            command = 'wp core config --dbname=%s --dbuser=%s --dbpass=%s --path=%s' % (dbNameRestore, dbUser, dbPassword, path)
            ProcessUtilities.executioner(command, website.externalApp)

            ## Exporting and importing database

            command = 'wp --allow-root --path=%s db export %s/dbexport-stage.sql' % (masterPath, path)
            ProcessUtilities.executioner(command)

            ## Import

            command = 'wp --allow-root --path=%s --quiet db import %s/dbexport-stage.sql' % (path, path)
            ProcessUtilities.executioner(command)

            try:
                command = 'rm -f %s/dbexport-stage.sql' % (path)
                ProcessUtilities.executioner(command)
            except:
                pass

            ## Sync WP-Content Folder

            command = 'rsync -avz %s/wp-content/ %s/wp-content/' % (masterPath, path)
            ProcessUtilities.executioner(command)

            ## Search and replace url

            command = 'wp search-replace --allow-root --path=%s "%s" "%s"' % (path, masterDomain, domain)
            ProcessUtilities.executioner(command)

            command = 'wp search-replace --allow-root --path=%s "www.%s" "%s"' % (path, masterDomain, domain)
            ProcessUtilities.executioner(command)

            logging.statusWriter(tempStatusPath, 'Fixing permissions..,90')

            from filemanager.filemanager import FileManager

            fm = FileManager(None, None)
            fm.fixPermissions(masterDomain)

            from plogical.installUtilities import installUtilities
            installUtilities.reStartLiteSpeed()

            logging.statusWriter(tempStatusPath, 'Completed,[200]')

            return 0
        except BaseException as msg:
            mesg = '%s. [168][404]' % (str(msg))
            logging.statusWriter(self.tempStatusPath, mesg)

    def startSyncing(self):
        try:
            tempStatusPath = self.extraArgs['tempStatusPath']
            childDomain = self.extraArgs['childDomain']
            #eraseCheck = self.extraArgs['eraseCheck']
            dbCheck = self.extraArgs['dbCheck']
            #copyChanged = self.extraArgs['copyChanged']


            child = ChildDomains.objects.get(domain=childDomain)
            masterPath = '/home/%s/public_html' % (child.master.domain)

            command = 'chmod 755 /home/%s/public_html' % (child.master.domain)
            ProcessUtilities.executioner(command)

            configPath = '%s/wp-config.php' % (child.path)

            if not os.path.exists(configPath):
                logging.statusWriter(tempStatusPath, 'WordPress is not detected. [404]')
                return 0

            ## Restore db

            logging.statusWriter(tempStatusPath, 'Syncing databases..,10')

            command = 'wp --allow-root --path=%s db export %s/dbexport-stage.sql' % (child.path, masterPath)
            ProcessUtilities.executioner(command)

            ## Restore to master domain

            command = 'wp --allow-root --path=%s --quiet db import %s/dbexport-stage.sql' % (masterPath, masterPath)
            ProcessUtilities.executioner(command)

            try:
                command = 'rm -f %s/dbexport-stage.sql' % (masterPath)
                ProcessUtilities.executioner(command)
            except:
                pass

            ## Sync WP-Content Folder

            logging.statusWriter(tempStatusPath, 'Syncing data..,50')

            command = 'rsync -avz %s/wp-content/ %s/wp-content/' % (child.path, masterPath)
            ProcessUtilities.executioner(command)

            ## Search and replace url

            command = 'wp search-replace --allow-root --path=%s "%s" "%s"' % (masterPath, child.domain, child.master.domain)
            ProcessUtilities.executioner(command)

            command = 'wp search-replace --allow-root --path=%s "www.%s" "%s"' % (masterPath, child.domain, child.master.domain)
            ProcessUtilities.executioner(command)

            from filemanager.filemanager import FileManager

            fm = FileManager(None, None)
            fm.fixPermissions(child.master.domain)

            from plogical.installUtilities import installUtilities
            installUtilities.reStartLiteSpeed()

            logging.statusWriter(tempStatusPath, 'Completed,[200]')

            return 0
        except BaseException as msg:
            mesg = '%s. [404]' % (str(msg))
            logging.statusWriter(tempStatusPath, mesg)
