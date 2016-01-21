from host import Host
from foreman.client import Foreman


HOSTS_COLLECTION = "hosts"

# Host status constants
FOREMAN_HOST_STATUS_NO_CHANGES = "No changes"
FOREMAN_HOST_STATUS_OUT_OF_SYNC = "Out of sync"
FOREMAN_HOST_STATUS_PENDING_INSTALLATION = "Pending Installation"


class ForemanException(Exception):
    pass


class ForemanHost(Host):
    """
    Foreman wrapper class
    """

    def __init__(
        self, host_ip, foreman_url, foreman_user,
        foreman_password, api_version=2
    ):
        """
        Initialize ForemanApi class

        :param host_ip: host ip
        :type host_ip: str
        :param foreman_url: foreman url
        :type foreman_url: str
        :param foreman_user: foreman user
        :type foreman_user: str
        :param foreman_password: foreman password
        :type foreman_password: str
        :param api_version: foreman api version
        :type api_version: int
        """
        super(ForemanHost, self).__init__(host_ip)
        self.foreman_api = Foreman(
            url=foreman_url,
            auth=(
                foreman_user, foreman_password
            ),
            api_version=api_version
        )
        self.host_id = self.get_element_id(self.fqdn, HOSTS_COLLECTION)

    def get_element_id(
        self, element_name, collection_name, search_attr="name"
    ):
        """
        Get element id from foreman collection

        :param element_name: element name
        :type element_name: str
        :param collection_name: foreman collection name
        :type collection_name: str
        :param search_attr: search by attr
        :type search_attr: str
        :return: element id
        :rtype: str
        """
        self.logger.info(
            "Looking for %s under foreman collection %s",
            element_name, collection_name
        )
        collection = getattr(self.foreman_api, collection_name)
        response = collection.index(
            search="%s = \"%s\"" % (search_attr, element_name)
        )
        if not response["results"]:
            self.logger.info(
                "Element '%s' is not declared under foreman collection %s",
                element_name, collection_name
            )
            return ""
        element = response["results"].pop()
        self.logger.info("Found element to use: %s", element["name"])
        return element["id"]

    def build(self):
        """
        Build host
        """
        self.update(build=True)

    def add(self, mac_address, **kwargs):
        """
        Add new host to foreman

        :param mac_address: host mac address
        :type mac_address: str
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
        :raise: ForemanException
        """
        host_d = {
            "name": self.fqdn,
            "mac": mac_address,
            "ip": self.ip
        }
        host_d.update(kwargs)
        try:
            self.foreman_api.hosts.create(host_d)
            self.host_id = self.get_element_id(self.fqdn, HOSTS_COLLECTION)
        except Exception as ex:
            raise ForemanException(
                "Failed to create host %s with parameters %s: %s" %
                (self.fqdn, kwargs, ex)
            )

    def update(self, **kwargs):
        """
        Update host in foreman

        :param kwargs: name = str
                       location_id = str
                       domain_id = str
                       organization_id = str
                       medium_id = str
                       architecture_id = str
                       operatingsystem_id = str
                       ptable_id = str
                       hostgroup_id = str
                       root_pass = str
                       managed = bool
        :raise: ForemanException
        """
        try:
            self.foreman_api.hosts.update(self.host_id, kwargs)
        except Exception as ex:
            raise ForemanException(
                "Failed to update host %s with parameters %s: %s" %
                (self.host_id, kwargs, ex)
            )

    def remove(self):
        """
        Remove host from foreman

        :raise: ForemanException
        """
        try:
            self.foreman_api.hosts.destroy(self.host_id)
            self.host_id = ""
        except Exception as ex:
            raise ForemanException(
                "Failed to remove host %s from foreman: %s" %
                (self.host_id, ex)
            )

    def get_status(self):
        """
        Get host status in foreman

        :return: host status
        :rtype: str
        :raise: HostedEngineException
        """
        host_status_d = self.foreman_api.hosts.status(self.host_id)
        if not host_status_d:
            self.logger.debug(
                "Failed to get host %s status" % self.host_id
            )
            return ""
        return host_status_d["status"]

    def is_exist(self):
        """
        Check if host exist under foreman

        :return: True, if host exist, otherwise False
        :rtype: bool
        """
        return True if self.host_id else False
