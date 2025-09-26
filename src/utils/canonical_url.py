"""
URL canonicalization utilities for NewsNexus Deduper

Provides functions to normalize URLs for comparison by removing
tracking parameters, normalizing domains, and standardizing format.
"""

import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Optional


class URLCanonicalizer:
    """Handles URL canonicalization for duplicate detection"""

    # Common tracking parameters to remove
    TRACKING_PARAMS = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'gclid', 'fbclid', 'msclkid', 'dclid', 'gclsrc',
        '_ga', '_gl', 'mc_eid', 'mc_cid',
        'ref', 'referrer', 'source', 'campaign',
        'WT.mc_id', 'WT.z_author', 'ncid'
    }

    # Common subdomains to normalize
    WWW_VARIANTS = {'www', 'www2', 'www3', 'm', 'mobile'}

    def __init__(self):
        pass

    def canonicalize_url(self, url: Optional[str]) -> Optional[str]:
        """
        Canonicalize a URL for comparison.

        Args:
            url: The URL to canonicalize

        Returns:
            Canonicalized URL string, or None if invalid
        """
        if not url or not isinstance(url, str):
            return None

        url = url.strip()
        if not url:
            return None

        try:
            # Add protocol if missing
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            # Parse the URL
            parsed = urlparse(url.lower())

            # Skip invalid URLs
            if not parsed.netloc:
                return None

            # Normalize the domain
            domain = self._normalize_domain(parsed.netloc)

            # Normalize the path
            path = self._normalize_path(parsed.path)

            # Clean query parameters
            query = self._clean_query_params(parsed.query)

            # Remove fragment (anchor)
            fragment = ''

            # Reconstruct the URL
            canonical = urlunparse((
                'https',  # Always use HTTPS
                domain,
                path,
                parsed.params,
                query,
                fragment
            ))

            return canonical

        except Exception:
            return None

    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain name"""
        domain = domain.lower().strip()

        # Remove port if it's default (80, 443)
        if ':80' in domain or ':443' in domain:
            domain = re.sub(r':(80|443)$', '', domain)

        # Handle www and mobile subdomains
        parts = domain.split('.')
        if len(parts) >= 3 and parts[0] in self.WWW_VARIANTS:
            # Remove common subdomains like www, m, mobile
            domain = '.'.join(parts[1:])

        return domain

    def _normalize_path(self, path: str) -> str:
        """Normalize URL path"""
        if not path or path == '/':
            return '/'

        # Remove trailing slash unless it's the root
        path = path.rstrip('/')
        if not path:
            path = '/'

        # Decode percent-encoded characters for common cases
        path = path.replace('%20', ' ')

        return path

    def _clean_query_params(self, query: str) -> str:
        """Remove tracking parameters from query string"""
        if not query:
            return ''

        try:
            params = parse_qs(query, keep_blank_values=False)

            # Remove tracking parameters
            cleaned_params = {
                key: value for key, value in params.items()
                if key.lower() not in self.TRACKING_PARAMS
            }

            # Sort parameters for consistent ordering
            if cleaned_params:
                return urlencode(sorted(cleaned_params.items()), doseq=True)
            else:
                return ''

        except Exception:
            return query  # Return original if parsing fails

    def urls_match(self, url1: Optional[str], url2: Optional[str]) -> bool:
        """
        Check if two URLs are equivalent after canonicalization.

        Args:
            url1: First URL
            url2: Second URL

        Returns:
            True if URLs match after canonicalization
        """
        canonical1 = self.canonicalize_url(url1)
        canonical2 = self.canonicalize_url(url2)

        if canonical1 is None or canonical2 is None:
            return False

        return canonical1 == canonical2

    def get_domain(self, url: Optional[str]) -> Optional[str]:
        """
        Extract normalized domain from URL.

        Args:
            url: URL to extract domain from

        Returns:
            Normalized domain or None if invalid
        """
        canonical = self.canonicalize_url(url)
        if not canonical:
            return None

        try:
            parsed = urlparse(canonical)
            return parsed.netloc
        except Exception:
            return None