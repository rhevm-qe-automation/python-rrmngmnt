import crypt
from host import Host
from user import RootUser
from resource import Resource
from foreman.client import Foreman

# Collection constants
COLLECTION = "collection"
FOREMAN_COLLECTION_OS = "operatingsystems"
FOREMAN_COLLECTION_HOST = "hosts"
FOREMAN_COLLECTION_ARCH = "architectures"
FOREMAN_COLLECTION_MEDIA = "media"
FOREMAN_COLLECTION_PTABLE = "ptables"
FOREMAN_COLLECTION_HOSTGROUP = "hostgroups"
FOREMAN_COLLECTION_ENVIRONMENT = "environments"

# Element id constants
ELEMENT_ID = "element_id"
OS_ID = "operatingsystem_id"
HOST_ID = "host_id"
ARCH_ID = "architecture_id"
MEDIA_ID = "medium_id"
PTABLE_ID = "ptable_id"
HOSTGROUP_ID = "hostgroup_id"
ENVIRONMENT_ID = "environment_id"

# Search attribute constants
SEARCH_ATTR = "search_attr"
SEARCH_ATTR_NAME = "name"
SEARCH_ATTR_TITLE = "title"
SEARCH_ATTR_DESCRIPTION = "description"

COLLECTION_D = {
    FOREMAN_COLLECTION_OS: {
        ELEMENT_ID: OS_ID,
        SEARCH_ATTR: SEARCH_ATTR_DESCRIPTION,
    },
    FOREMAN_COLLECTION_HOST: {
        ELEMENT_ID: HOST_ID,
        SEARCH_ATTR: SEARCH_ATTR_NAME,
    },
    FOREMAN_COLLECTION_ARCH: {
        ELEMENT_ID: ARCH_ID,
        SEARCH_ATTR: SEARCH_ATTR_NAME,
    },
    FOREMAN_COLLECTION_MEDIA: {
        ELEMENT_ID: MEDIA_ID,
        SEARCH_ATTR: SEARCH_ATTR_NAME,
    },
    FOREMAN_COLLECTION_PTABLE: {
        ELEMENT_ID: PTABLE_ID,
        SEARCH_ATTR: SEARCH_ATTR_NAME,
    },
    FOREMAN_COLLECTION_HOSTGROUP: {
        ELEMENT_ID: HOSTGROUP_ID,
        SEARCH_ATTR: SEARCH_ATTR_TITLE,
    },
    FOREMAN_COLLECTION_ENVIRONMENT: {
        ELEMENT_ID: ENVIRONMENT_ID,
        SEARCH_ATTR: SEARCH_ATTR_NAME,
    }
}

# Host status constants
FOREMAN_HOST_STATUS_NO_CHANGES = "No changes"
FOREMAN_HOST_STATUS_OUT_OF_SYNC = "Out of sync"
FOREMAN_HOST_STATUS_PENDING_INSTALLATION = "Pending Installation"


class ForemanException(Exception):
    pass


class ForemanCollection(Resource):
    """
    Foreman collection class
    """
    def __init__(
        self, collection_name, foreman_url, foreman_user, foreman_password,
        api_version=2, search_attr=None
    ):
        """
        Initialize Foreman collection class

        :param collection_name: foreman collection name
        :type collection_name: str
        :param foreman_url: foreman url
        :type foreman_url: str
        :param foreman_user: foreman user
        :type foreman_user: str
        :param foreman_password: foreman password
        :type foreman_password: str
        :param api_version: foreman api version
        :type api_version: int
        :param search_attr: search element under collection by given attribute
        :type search_attr: str
        """
        super(ForemanCollection, self).__init__()
        self.foreman_api = Foreman(
            url=foreman_url,
            auth=(foreman_user, foreman_password),
            api_version=api_version
        )
        self.collection_name = collection_name
        if self.collection_name:
            self.collection = getattr(self.foreman_api, self.collection_name)
        if not search_attr:
            self.search_attr = COLLECTION_D[
                self.collection_name
            ][SEARCH_ATTR]

    def get_element_id(self, element_name):
        """
        Get element id from foreman collection

        :param element_name: element name
        :type element_name: str
        :return: element id
        :rtype: str
        """
        self.logger.info(
            "Looking for %s under foreman collection %s",
            element_name, self.collection_name
        )
        response = self.collection.index(
            search="%s = \"%s\"" % (self.search_attr, element_name)
        )
        try:
            return response["results"][0]["id"]
        except (IndexError, KeyError):
            self.logger.info(
                "Element '%s' is not declared under foreman collection %s",
                element_name, self.collection_name
            )
            return ""

    def add(self, **kwargs):
        """
        Add new element to foreman collection

        :param kwargs: element parameters
        :raise: ForemanException
        """
        try:
            self.collection.create(kwargs)
        except Exception as ex:
            raise ForemanException(
                "Failed to add element with parameters %s: %s" % (kwargs, ex)
            )

    def update(self, element_name, **kwargs):
        """
        Update element in foreman collection

        :param element_name: element name
        :type element_name: str
        :param kwargs: element parameters to update
        :raise: ForemanException
        """
        element_id = self.get_element_id(element_name=element_name)
        try:
            self.collection.update(element_id, kwargs)
        except Exception as ex:
            raise ForemanException(
                "Failed to update element %s with parameters %s: %s" %
                (element_name, kwargs, ex)
            )

    def remove(self, element_name):
        """
        Remove element from foreman collection

        :param element_name: element name
        :type element_name: str
        :raise: ForemanException
        """
        element_id = self.get_element_id(element_name=element_name)
        try:
            self.collection.destroy(element_id)
        except Exception as ex:
            raise ForemanException(
                "Failed to remove element %s from foreman: %s" %
                (element_name, ex)
            )

    def is_exist(self, element_name):
        """
        Check if element exist under foreman collection

        :param element_name: element name
        :type element_name: str
        :return: True, if element exist, otherwise False
        :rtype: bool
        """
        return bool(self.get_element_id(element_name=element_name))

    def get_status(self, element_name):
        """
        Get element status

        :param element_name: element name
        :type element_name: str
        :return: element status
        :rtype: str
        """
        element_id = self.get_element_id(element_name=element_name)
        element_status_d = self.collection.status(element_id)
        if not element_status_d:
            self.logger.debug(
                "Failed to get element %s status" % element_name
            )
            return ""
        return element_status_d["status"]


class ForemanHost(Host):
    """
    Foreman host class
    """
    def __init__(
        self, host_ip, host_root_password,
        foreman_url, foreman_user, foreman_password
    ):
        """
        Initialize foreman host class

        :param host_ip: host ip
        :type host_ip: str
        :param host_root_password: host root password
        :type host_root_password: str
        :param foreman_url: foreman url
        :type foreman_url: str
        :param foreman_user: foreman user
        :type foreman_user: str
        :param foreman_password: foreman password
        :type foreman_password: str
        """
        super(ForemanHost, self).__init__(ip=host_ip)
        self.users.append(RootUser(password=host_root_password))
        self.f_host_collection = ForemanCollection(
            collection_name=FOREMAN_COLLECTION_HOST,
            foreman_url=foreman_url,
            foreman_user=foreman_user,
            foreman_password=foreman_password,
        )

    def add_to_foreman(self, **kwargs):
        """
        Add host to foreman

        :param kwargs: mac = str
                       location_id = str
                       domain_id = str
                       organization_id = str
                       medium_id = str
                       architecture_id = str
                       operatingsystem_id = str
                       ptable_id = str
                       hostgroup_id = str
                       build = bool
                       managed = bool
        """
        mac_address = kwargs.pop("mac", self.network.get_mac_by_ip(self.ip))
        host_d = {
            "name": self.fqdn,
            "mac": mac_address,
            "ip": self.ip,
            "root_pass": crypt.crypt(self.root_user.password, "$1$redhat")
        }
        host_d.update(kwargs)
        self.f_host_collection.add(**host_d)

    def update(self, **kwargs):
        """
        Update host in foreman

        :param kwargs: location_id = str
                       domain_id = str
                       organization_id = str
                       medium_id = str
                       architecture_id = str
                       operatingsystem_id = str
                       ptable_id = str
                       hostgroup_id = str
                       build = bool
                       root_pass = str
                       managed = bool
        """
        self.f_host_collection.update(element_name=self.fqdn, **kwargs)

    def remove(self):
        """
        Remove host from foreman
        """
        self.f_host_collection.remove(element_name=self.fqdn)

    def build(self):
        """
        Build host
        """
        self.update(build=True)
