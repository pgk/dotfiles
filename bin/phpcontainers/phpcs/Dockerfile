FROM php:7.3-alpine

# Install the WordPress rules
ENV WPCS_VERSION 2.3.0
ENV PHP_COMPATIBILITY_VERSION 9.3.5
ENV PHPCS_VERSION 3.3.1
ADD standards /standards

# Required by phpcbf
RUN apk add --no-cache patch

# To build under proxy, use: docker build --build-arg "http_proxy=$http_proxy" 
RUN if test -n "$http_proxy"; then pear config-set http_proxy "$http_proxy"; fi

RUN pear install PHP_CodeSniffer-${PHPCS_VERSION}

RUN phpcs --config-set installed_paths /standards/WordPress-Coding-Standards-${WPCS_VERSION},/standards/PHPCompatibility-${PHP_COMPATIBILITY_VERSION}
