import requests
from bs4 import BeautifulSoup

class OpportunityHunter:

    def search_linkedin(self,keyword):

        url=f"https://www.linkedin.com/search/results/all/?keywords={keyword}"

        return {
            "platform":"linkedin",
            "keyword":keyword,
            "url":url
        }


    def search_startups(self,keyword):

        url=f"https://www.crunchbase.com/discover/organization.companies?q={keyword}"

        return {
            "platform":"crunchbase",
            "keyword":keyword,
            "url":url
        }


    def search_internet(self,keyword):

        url=f"https://www.google.com/search?q={keyword}+opportunity"

        return {
            "platform":"google",
            "keyword":keyword,
            "url":url
        }
