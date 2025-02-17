package com.sismics.reader.core.dao.file.rss;

import com.sismics.reader.core.model.jpa.Article;
import com.sismics.reader.core.model.jpa.Feed;
import org.xml.sax.InputSource;
import org.xml.sax.SAXException;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.Reader;

import javax.xml.parsers.SAXParser;
import javax.xml.parsers.SAXParserFactory;


import java.util.*;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;

/**
 * RssReader is the public API that parses a feed (RSS, Atom, or RDF)
 * into a Feed object and a list of Articles.
 */
public class RssReader {
    // Date formatters – you may adjust or add more patterns as needed.
    

    // The specialized parser that was chosen
    private AbstractFeedParser parser;

    /**
     * Reads the feed from an InputStream. The method detects the feed type,
     * instantiates the proper specialized parser, and then parses the entire feed.
     *
     * @param is the InputStream (may be GZIP’ed) containing the XML feed.
     * @throws Exception if any error occurs during parsing.
     */
    public void readRssFeed(InputStream is) throws Exception {
        // Buffer the stream completely so that we can do a pre-scan.
        byte[] bytes = readFully(is);
        ByteArrayInputStream bis1 = new ByteArrayInputStream(bytes);
        ByteArrayInputStream bis2 = new ByteArrayInputStream(bytes);

        // Use a small SAX parser to detect the root element name.
        String rootElementName = detectFeedType(bis1);
        if ("rss".equalsIgnoreCase(rootElementName)) {
            parser = new RssFeedParser();
        } else if ("feed".equalsIgnoreCase(rootElementName)) {
            parser = new AtomFeedParser();
        } else if ("RDF".equalsIgnoreCase(rootElementName)) {
            parser = new RdfFeedParser();
        } else {
            throw new Exception("Unknown feed type: " + rootElementName);
        }

        // Create and configure the SAX parser.
        SAXParserFactory factory = SAXParserFactory.newInstance();
        factory.setNamespaceAware(true);
        // (Disable DTD loading and continue after fatal errors)
        factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
        factory.setFeature("http://apache.org/xml/features/continue-after-fatal-error", true);
        SAXParser saxParser = factory.newSAXParser();

        // Wrap the byte stream in our XmlReader (which simply chooses the encoding)
        Reader reader = new XmlReader(bis2, "UTF-8");
        InputSource inputSource = new InputSource(reader);
        saxParser.parse(inputSource, parser);

        // Perform any post-parsing fixes/validations.
        parser.fixGuid();
        parser.validateFeed();
    }

    /**
     * Returns the parsed Feed.
     */
    public Feed getFeed() {
        return parser != null ? parser.getFeed() : null;
    }

    /**
     * Returns the list of parsed Articles.
     */
    public List<Article> getArticleList() {
        return parser != null ? parser.getArticleList() : null;
    }


    /**
     * Reads the entire InputStream into a byte array.
     */
    private byte[] readFully(InputStream is) throws IOException {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] data = new byte[4096];
        int n;
        while ((n = is.read(data)) != -1) {
            buffer.write(data, 0, n);
        }
        return buffer.toByteArray();
    }

    /**
     * Quickly detects the root element name by doing a minimal SAX parse.
     */
    private String detectFeedType(InputStream is) throws Exception {
        SAXParserFactory factory = SAXParserFactory.newInstance();
        factory.setNamespaceAware(true);
        SAXParser saxParser = factory.newSAXParser();
        FeedTypeDetector detector = new FeedTypeDetector();
        InputSource inputSource = new InputSource(new InputStreamReader(is, "UTF-8"));
        try {
            saxParser.parse(inputSource, detector);
        } catch (SAXException ex) {
            // We deliberately throw an exception to stop parsing after the first element.
            if (!"StopParsing".equals(ex.getMessage())) {
                throw ex;
            }
        }
        return detector.getRootElementName();
    }

}

    
    


