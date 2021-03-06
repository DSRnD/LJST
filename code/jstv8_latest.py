# -*- coding: utf-8 -*-
"""
Created on Mon Mar 18 14:08:11 2019

@author: granjan
"""

# -*- coding: utf-8 -*-
"""
Created on Mon Mar 11 13:16:20 2019

@author: granjan
"""
from time import time
import numpy as np
import pandas as pd
import nltk
from nltk.corpus import stopwords
from nltk.stem.porter import PorterStemmer
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import MinMaxScaler
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from sklearn.metrics import mean_squared_error
from itertools import combinations
from toolz import compose
from sklearn.model_selection import train_test_split
import scipy
from scipy.special import gammaln, psi
from hyperopt import fmin, tpe, hp, Trials, STATUS_OK, space_eval
import ast
import re

#import re
MAX_VOCAB_SIZE = 50000


def sampleFromDirichlet(alpha):
    """
    Sample from a Dirichlet distribution
    alpha: Dirichlet distribution parameter (of length d)
    Returns:
    x: Vector (of length d) sampled from dirichlet distribution
    """
    return np.random.dirichlet(alpha)


def sampleFromCategorical(theta):
    """
    Samples from a categorical/multinoulli distribution
    theta: parameter (of length d)
    Returns:
    x: index ind (0 <= ind < d) based on probabilities in theta
    """
    theta = theta/np.sum(theta)
    return np.random.multinomial(1, theta).argmax()


def word_indices(wordOccuranceVec):
    """
    Turn a document vector of size vocab_size to a sequence
    of word indices. The word indices are between 0 and
    vocab_size-1. The sequence length is equal to the document length.
    """
    for idx in wordOccuranceVec.nonzero()[0]:
        for i in range(int(wordOccuranceVec[idx])):
            yield idx


class SentimentLDAGibbsSampler:

    def __init__(self, numTopics, alpha, beta, gamma, numSentiments=100, minlabel=0, maxlabel=10, SentimentRange = 10):
        """
        numTopics: Number of topics in the model
        numSentiments: Number of sentiments (default 2)
        alpha: Hyperparameter for Dirichlet prior on topic distribution
        per document
        beta: Hyperparameter for Dirichlet prior on vocabulary distribution
        per (topic, sentiment) pair
        gamma:Hyperparameter for Dirichlet prior on sentiment distribution
        per (document, topic) pair
        """
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.numTopics = numTopics
        self.numSentiments = numSentiments
        self.SentimentRange = SentimentRange
        self.probabilities_ts = {}
        self.minlabel = minlabel
        self.maxlabel = maxlabel
        # review = review.decode("ascii", "ignore").encode("ascii")

    def processReviews(self, reviews):
        #self.vectorizer = SkipGramVectorizer(analyzer="word",stop_words="english",max_features=MAX_VOCAB_SIZE,max_df=.75,min_df=10, k = window,ngram_range=(1,1))
        self.vectorizer = CountVectorizer(analyzer="word",tokenizer=None,preprocessor=None,stop_words="english",max_features=MAX_VOCAB_SIZE,max_df=.5,min_df=5)
        train_data_features = self.vectorizer.fit_transform(reviews)
        words = self.vectorizer.get_feature_names()
        self.vocabulary = dict(zip(words,np.arange(len(words))))
        self.inv_vocabulary = dict(zip(np.arange(len(words)),words))
        wordOccurenceMatrix = train_data_features.toarray()
        return wordOccurenceMatrix
        
    def create_priorsentiment(self):
        sid = SentimentIntensityAnalyzer()
        l = []
        binsize = self.SentimentRange*1.0/self.numSentiments
        for i in self.vocabulary:
            l.append(sid.polarity_scores(i).get('compound',np.nan))
        clf = MinMaxScaler(feature_range = (self.minlabel,self.maxlabel))
        l = clf.fit_transform(np.array(l))
        l = [min(int(i/binsize)-1,0) for i in l]
        self.priorSentiment = dict(zip(list(self.vocabulary.keys()),l))

    def _initialize_(self, reviews, labels, unlabeled_reviews):
        """
        wordOccuranceMatrix: numDocs x vocabSize matrix encoding the
        bag of words representation of each document
        """
        allreviews = reviews + unlabeled_reviews
        self.wordOccuranceMatrix = self.processReviews(allreviews)
        #self.create_priorsentiment()
        numDocs, vocabSize = self.wordOccuranceMatrix.shape
        
        numDocswithlabels = len(labels)
        # Pseudocounts
        self.n_dt = np.zeros((numDocs, self.numTopics))
        self.n_ds = np.zeros((numDocs, self.numSentiments))
        self.ds_distribution = np.zeros((numDocs, self.numSentiments))

        self.n_dst = np.zeros((numDocs, self.numSentiments,self.numTopics,))
        self.n_d = np.zeros((numDocs))
        self.n_vts = np.zeros((vocabSize, self.numTopics, self.numSentiments))
        self.n_ts = np.zeros((self.numTopics, self.numSentiments))
        self.dt_distribution = np.zeros((numDocs, self.numTopics))
        self.dst_distribution = np.zeros((numDocs, self.numSentiments,self.numTopics ))
        self.topics = {}
        self.sentiments = {}
        self.priorSentiment = {}

        self.alphaVec = self.alpha.copy()
        self.gammaVec = self.gamma.copy()


        for d in range(numDocs):
            
            sentimentDistribution = sampleFromDirichlet(self.gammaVec)
            topicDistribution = np.zeros(( self.numSentiments,self.numTopics))
            for s in range(self.numSentiments):
                topicDistribution[s, :] = sampleFromDirichlet(self.alphaVec)
            for i, w in enumerate(word_indices(self.wordOccuranceMatrix[d, :])):
               
                   s = sampleFromCategorical(sentimentDistribution)
                   t = sampleFromCategorical(topicDistribution[s, :])
                  
                   prior_sentiment1 = lexicon_dict.get(w,1)
                   
                   self.topics[(d, i)] = t
                   self.sentiments[(d, i)] = s
                   self.n_dt[d, t] += 1
                   self.n_ds[d,s]+=1
                   self.n_dst[d,s,t] += 1
                   self.n_d[d] += 1
                   self.n_vts[w, t, s*prior_sentiment1] += 1
                   self.n_ts[t, s] += 1
                   self.ds_distribution[d,:] = (self.n_ds[d] + self.gammaVec) / \
	                (self.n_d[d] + np.sum(self.gammaVec))
                    
                   self.dst_distribution[d,:,:] = (self.n_dst[d, :, :] + self.alphaVec) / \
	                (self.n_ds[d, :] + np.sum(self.alphaVec))[:,np.newaxis]

    def conditionalDistribution(self, d, v):
        """
        Calculates the (topic, sentiment) probability for word v in document d
        Returns:    a matrix (numTopics x numSentiments) storing the probabilities
        """
        probabilities_ts = np.ones((self.numTopics, self.numSentiments))
        firstFactor = (self.n_ds[d] + self.gammaVec) / \
            (self.n_d[d] +  np.sum(self.gammaVec))
        secondFactor = np.zeros((self.numTopics,self.numSentiments))
        for s in range(self.numSentiments):
        
             secondFactor = ((self.n_dst[d, s, :] + self.alphaVec) / \
            (self.n_ds[d, s] + np.sum(self.alphaVec)))[:,np.newaxis]
        thirdFactor = (self.n_vts[v,:, :] + self.beta) / \
            (self.n_ts + self.n_vts.shape[0] * self.beta)
        probabilities_ts = firstFactor[:, np.newaxis]
        probabilities_ts = secondFactor * thirdFactor
        probabilities_ts /= np.sum(probabilities_ts)
        return probabilities_ts

    

    def getTopKWords(self, K):
        """
        Returns top K discriminative words for topic t and sentiment s
        ie words v for which p(v | t, s) is maximum
        """
        pseudocounts = np.copy(self.n_vts)
        normalizer = np.sum(pseudocounts, (0))
        pseudocounts /= normalizer[np.newaxis, :, :]
        worddict = {}
        for t in range(self.numTopics):
            worddict[t] = {}
            for s in range(self.numSentiments):
                topWordIndices = pseudocounts[:, t, s].argsort()[-1:-(K + 1):-1]
                vocab = self.vectorizer.get_feature_names()
                worddict[t][s] = [vocab[i] for i in topWordIndices]
        return worddict
    def getTopKWordsperTopic(self, K):
        pseudocounts = np.copy(self.n_vts)
        normalizer = np.sum(pseudocounts, (0))
        pseudocounts /= normalizer[np.newaxis, :, :]
        worddict = {}
        vocab = self.vectorizer.get_feature_names()
        for t in range(self.numTopics):
            worddict[t] = set()
            topWordIndices = list(pseudocounts[:, t, :].ravel().argsort()%self.n_vts.shape[0])
            topWordIndices.reverse()
            for i in topWordIndices:
                if len(worddict[t]) < K:
                    worddict[t].add(vocab[i])

        return worddict

    def run(self, reviews, labels, unlabeled_reviews, maxIters=100):
        """
        Runs Gibbs sampler for sentiment-LDA
        """
        self._initialize_(reviews, labels, unlabeled_reviews)
        self.loglikelihoods = np.zeros(maxIters)
        numDocs, vocabSize = self.wordOccuranceMatrix.shape
        for iteration in range(maxIters):
            print ("Starting iteration %d of %d" % (iteration + 1, maxIters))
            loglikelihood = 0
            for d in range(numDocs):
                for i, v in enumerate(word_indices(self.wordOccuranceMatrix[d, :])):
                    t = self.topics[(d, i)]
                    s = self.sentiments[(d, i)]
                    prior_sentiment1 = lexicon_dict.get(v,1)
                    self.n_dt[d, t] -= 1
                    self.n_ds[d,s]-=1
                    self.n_d[d] -= 1
                    self.n_dst[d,s,t] -= 1
                    self.n_vts[v, t, s*prior_sentiment1] -= 1
                    self.n_ts[t, s] -= 1

                    probabilities_ts = self.conditionalDistribution(d, v)
                    #if v in self.priorSentiment:
                       #s = self.priorSentiment[v]
                       #t = sampleFromCategorical(probabilities_ts[:, s])
                    #else:
                    ind = sampleFromCategorical(probabilities_ts.flatten())
                    t, s = np.unravel_index(ind, probabilities_ts.shape)

                    self.probabilities_ts[(d,v)] = probabilities_ts[t,s]
                    #loglikelihood += np.log(self.probabilities_ts[(d,v)])
                    
                    self.topics[(d, i)] = t
                    self.sentiments[(d, i)] = s
                    self.n_dt[d, t] += 1
                    self.n_d[d] += 1
                    self.n_dst[d,s,t] += 1
                    self.n_vts[v, t, s*prior_sentiment1] += 1
                    self.n_ts[t, s] += 1
                    self.n_ds[d,s]+=1
                    
                if iteration == maxIters - 1:
	                self.ds_distribution[d,:] = (self.n_ds[d,:] + self.gammaVec) / \
	                (self.n_d[d] + np.sum(self.gammaVec))
	                self.dst_distribution[d,:,:] = (self.n_dst[d, :, :] + self.alphaVec) / \
	                (self.n_ds[d, :] + np.sum(self.alphaVec))[:,np.newaxis]
            
	                self.ds_distribution = self.ds_distribution/np.sum(self.ds_distribution, axis=1)[:,np.newaxis]
	                self.dst_distribution = self.dst_distribution/np.sum(self.dst_distribution, axis=2)[:,:,np.newaxis]
                #loglikelihood += np.sum(gammaln((self.n_dt[d] + self.alphaVec))) - gammaln(np.sum((self.n_dt[d] + self.alphaVec)))
                #loglikelihood -= np.sum(gammaln(self.alphaVec)) - gammaln(np.sum(self.alphaVec))
                
                #for k in range(self.numTopics):
                #    loglikelihood += np.sum(gammaln((self.n_dts[d, k, :] + self.gammaVec))) - gammaln(np.sum(self.n_dts[d, k, :] + self.gammaVec))
                #    loglikelihood -= np.sum(gammaln(self.gammaVec)) - gammaln(np.sum(self.gammaVec))
            
            #for k in range(self.numTopics):
            #    for l in range(self.numSentiments):
            #        loglikelihood += (np.sum(gammaln((self.n_vts[:, k,l] + self.beta))) - gammaln(np.sum((self.n_vts[:, k,l] + self.beta))))
            #        loglikelihood -= (vocabSize * gammaln(self.beta) - gammaln(vocabSize * self.beta))

            #self.loglikelihoods[iteration] = loglikelihood 
            #print ("Total loglikelihood is {}".format(loglikelihood))
            
           ## if (iteration+1)%5 == 0:
                # ADJUST ALPHA BY USING MINKA'S FIXED-POINT ITERATION
                #numerator = 0
                #denominator = 0
                #for d in range(numDocs):
                    #numerator += psi(self.n_d[d] + self.alphaVec) - psi(self.alphaVec)
                    #denominator += psi(np.sum(self.n_dt[d] + self.alphaVec)) - psi(np.sum(self.alphaVec))
                
                #self.alphaVec *= numerator / denominator     
                #self.alphaVec = np.maximum(self.alphaVec,self.alpha)

def mape_score(y_true, y_pred):
    l = []
    assert len(y_true) == len(y_pred)
    for i in range(len(y_true)):
        if y_true[i] != 0:
            l.append(np.abs(1-y_pred[i]/y_true[i])*100)
    return np.mean(l)
    
def post_processing(text, index, sampler, worddict):
    #topicindices = np.argwhere(sampler.dt_distribution[index]>0)
    #topicsentiment = np.argwhere(sampler.dts_distribution[index][topicindices] >= 1)
    toptopic = np.argmax(sampler.ds_distribution[index])
    print ("Document id {} has top topic id {}".format(index, toptopic))

def coherence_score(sampler,topic_sentiment_df):
    totalcnt = topic_sentiment_df.shape[0]
    total = 0
    for i in range(len(topic_sentiment_df)):
        allwords = topic_sentiment_df.top_words.iloc[i] #ast.literal_eval(topic_sentiment_df.top_words.iloc[i])
        for word1 in allwords:
            for word2 in allwords:
                if word1 != word2:
                    ind1 = sampler.vocabulary[word1]
                    ind2 = sampler.vocabulary[word2]
                    total += np.log((np.matmul(sampler.wordOccuranceMatrix[:,ind1],sampler.wordOccuranceMatrix[:,ind2]) + 1)/np.sum(sampler.wordOccuranceMatrix[:,ind2]))
    return total/(2*totalcnt)

def kl_score(pk,qk):
    return (scipy.stats.entropy(pk,qk)*.5 + scipy.stats.entropy(qk,pk)*.5)
        
def run_experiment(numsentilabel,numtopics,alpha,beta,gamma,maxiter,numwordspertopic):
    global sampler, ds_estimated, rmse, coh_score, topic_sentiment_df
    
    binsize = sentirange/numsentilabel
    alpha = alpha/numtopics * np.ones(numtopics)
    gamma = [gamma/(numtopics * numsentilabel)]*numsentilabel
    
    sampler = SentimentLDAGibbsSampler(numtopics, alpha, beta, gamma, numsentilabel, minlabel, maxlabel, sentirange)
    t0 = time()
    sampler.run(list(train_review),list(train_sentiment), list(test_review), maxiter)
    worddict = sampler.getTopKWords(numwordspertopic)
    print("done in %0.3fs." % (time() - t0))
    
    ds_estimated = []
    for i in range(len(test_review)):
        sentiment = 0
        index = len(train_review) + i
        temp =(sampler.ds_distribution[index,:])
        for k, val in enumerate(temp):
            sentiment += (k+1)*binsize*val
        ds_estimated.append(sentiment)
    
    #print ("mean square error and mean absolute percentage error in sentiment estimation are {}, {}%".format(np.sqrt(mean_squared_error(np.array(test_sentiment.values)/10, np.array(ds_estimated)/10)), mape(test_sentiment.values, ds_estimated)))

    temp = []
    for t in range(numtopics):
        for s in range(numsentilabel):
            temp.append([t,s,worddict[t][s]])
    
    topic_sentiment_df = pd.DataFrame(temp,columns = ["topic_id","sentiment_label","top_words"])
    
    #for i in range(0,5):
    #    index = len(train_review) + i
    #    post_processing(test_review.iloc[i],index,sampler,worddict)
    #    save_document_image('../output/{}_review_rjst_{}.png'.format(review_data_file.split('/')[-1].replace('.csv',''),index+1),sampler.dts_distribution[index,:,:])
      
    rmse = np.sqrt(mean_squared_error(np.array(test_sentiment.values)/10, np.array(ds_estimated)/10))
    coh_score = coherence_score(sampler,topic_sentiment_df)
    
    mape = mape_score(test_sentiment.values, ds_estimated)
    
    testlen = test_review.shape[0]
    document_topic = np.zeros((testlen,numtopics))
    for d in range(train_review.shape[0],sampler.ds_distribution.shape[0]):
        document_topic[d-train_review.shape[0],np.matmul(sampler.ds_distribution[d,:],sampler.dst_distribution[d,:,:]).argmax()] = 1
    all_kl_scores = np.zeros((testlen,testlen))
    for i in range(testlen-1):
        for j in range(i+1,testlen):
            score = kl_score(np.matmul(sampler.ds_distribution[train_review.shape[0]+i,:],sampler.dst_distribution[train_review.shape[0]+i,:,:]),np.matmul(sampler.ds_distribution[train_review.shape[0]+j,:],sampler.dst_distribution[train_review.shape[0]+j,:,:]))
            all_kl_scores[i,j] = score
            all_kl_scores[j,i] = score

    intradist = 0
    for i in range(numtopics):
       cnt = document_topic[:,i].sum()
       tmp = np.outer(document_topic[:,i],document_topic[:,i])
       tmp = tmp * all_kl_scores
       intradist += tmp.sum()*1.0/(cnt*(cnt-1))
    intradist = intradist/numtopics

    interdist = 0
    for i in range(numtopics):
       for j in range(numtopics):
           if i != j:
             cnt_i = document_topic[:,i].sum()
             cnt_j = document_topic[:,j].sum()
             tmp = np.outer(document_topic[:,i],document_topic[:,j])
             tmp = tmp * all_kl_scores
             interdist += tmp.sum()*1.0/(cnt_i*cnt_j)
    interdist = interdist/(numtopics*(numtopics-1))
    H_score = intradist/interdist
    document_topic[:2].sum()
   
    print ("RMSE, MAPE, Coherence ,Hscore values are {},{}%,{},{}".format(rmse,mape,coh_score,H_score))
  
    return rmse, coh_score
  
def f1(params):
    numsentilabel,numtopics = params['numsentilabel'], params['numtopics']
    print (numsentilabel,numtopics,alpha,beta,gamma,maxiter,numwordspertopic)
    return run_experiment(numsentilabel,numtopics,alpha,beta,gamma,maxiter,numwordspertopic)[0]
    
def f2(params):
    global topic_sentiment_df
    numwordspertopic = params['numwordspertopic']
    print (numwordspertopic)
    worddict = sampler.getTopKWords(numwordspertopic)
    temp = []
    for t in range(numtopics):
        for s in range(numsentilabel):
            temp.append([t,s,worddict[t][s]])
    
    topic_sentiment_df = pd.DataFrame(temp,columns = ["topic_id","sentiment_label","top_words"])
    coh_score = coherence_score(sampler,topic_sentiment_df)
    print (coh_score)
    return -1*coh_score    

def clean(review_data):
    try:
        stop_free = " ".join([st.stem(i) for i in review_data.lower().split() if i not in stop])
        punc_free = ''.join(ch for ch in stop_free if ch not in exclude)
        normalized = " ".join(lemma.lemmatize(word) for word in punc_free.split())
        return normalized
    except:
        return review_data
        
def processSingleReview(review, d=None):
    """
    Convert a raw review to a string of words
    """
    letters_only = re.sub("[^a-zA-Z]", " ", review)
    words = letters_only.lower().split()
    stops = set(stopwords.words("english"))
    meaningful_words = [st.stem(w) for w in words if w not in stops]
    meaningful_words = [w for w in meaningful_words if pos_tag([w],tagset='universal')[0][1] in ['NOUN','VERB','ADJ']] #
    return(" ".join(meaningful_words))
    
if __name__ == '__main__':

    ''' Fixed parameters '''
    minlabel = 0
    maxlabel = 10
    sentirange = maxlabel - minlabel
    numwordspertopic = 5
    
    ''' Hyperparameters '''
    numsentilabel = 10
    numtopics = 20
    alpha = 10.0
    beta = .01
    gamma = 10.0
    maxiter = 10
    
    testsize = .2
    review_data_file = 'yelp50.csv'
   
    lexicon_data = pd.read_excel('C:/Users/asengup6/Documents/Work/Research/LJST/data/prior_sentiment.xlsx')
    lexicon_data.columns = ['Word','Sentiment']
    lexicon_data['clean_word'] = lexicon_data.apply(lambda row :clean(row['Word']),axis=1)
    lexicon_dict = dict(zip(lexicon_data['clean_word'],lexicon_data['Sentiment']))
    
    review_data = pd.read_csv(review_data_file,encoding='cp1250')   

    train_review, test_review, train_sentiment, test_sentiment = train_test_split(review_data.clean_sentence, review_data.sentiment_score, test_size=testsize,random_state=123)
    train_review = train_review.reset_index(drop=True)
    test_review = test_review.reset_index(drop=True)
    
    #run_experiment(numsentilabel,numtopics,alpha,beta,gamma,maxiter)
    for numtopics in [10,20,50,100]:
        run_experiment(numsentilabel,numtopics,alpha,beta,gamma,maxiter,numwordspertopic)
    
    numtopics = 10
    for numsentilabel in [10,20,50,100]:
        run_experiment(numsentilabel,numtopics,alpha,beta,gamma,maxiter,numwordspertopic)

    #run_experiment(numsentilabel,numtopics,alpha,beta,gamma,maxiter)
    
    '''
    document_topic = np.zeros(sampler.dt_distribution.shape)
    for d in range(document_topic.shape[0]):
        document_topic[d,sampler.dt_distribution[d,:].argmax()] = 1
     
    all_kl_scores = np.zeros((sampler.wordOccuranceMatrix.shape[0],sampler.wordOccuranceMatrix.shape[0]))
    for i in range(sampler.wordOccuranceMatrix.shape[0]-1):
        for j in range(i+1,sampler.wordOccuranceMatrix.shape[0]):
            score = kl_score(sampler.dt_distribution[i],sampler.dt_distribution[j])
            all_kl_scores[i,j] = score
            all_kl_scores[j,i] = score
    
    h_score = 0
    for i in range(numtopics):
        cnt = document_topic[:,i].sum()
        tmp = np.outer(document_topic[:,i],document_topic[:,i])
        tmp = tmp * all_kl_scores
        h_score += tmp.sum()*1.0/(cnt*(cnt-1))
    h_score = h_score/numtopics
    
    spacetosearch = {
    'numsentilabel': hp.choice('numsentilabel', [10,20,50]),
    'numtopics': hp.choice('numtopics', [10,20,50]),
    }
    
    trials = Trials()
    best = fmin(f1, spacetosearch, algo=tpe.suggest, max_evals=9, trials=trials)
    best_params1 = space_eval(spacetosearch, best)
    print ('best {} with params {}'.format(best, best_params1))
    numsentilabel,numtopics = best_params1['numsentilabel'], best_params1['numtopics']
    run_experiment(numsentilabel,numtopics,alpha,beta,gamma,maxiter,numwordspertopic)
    
    spacetosearch = {
    'numwordspertopic': hp.choice('numwordspertopic', [5,10,20,25,50])
    }
    
    trials = Trials()
    best = fmin(fn=f2, space=spacetosearch, algo=tpe.suggest, trials=trials, max_evals=5)
    best_params2 = space_eval(spacetosearch, best)
    print ('best {} with params {}'.format(best, best_params2))
    numwordspertopic = best_params2['numwordspertopic']
    
    #run_experiment(numsentilabel,numtopics,alpha,beta,gamma,maxiter,5)
    topic_sentiment_df.to_csv(review_data_file.replace('.csv',"_{}_iter_output_rjst.csv".format(maxiter)), index=False)
    #train_review, test_review, train_sentiment, test_sentiment = train_test_split(review_data.clean_sentence, review_data.sentiment_score, test_size=.1,random_state=123)
    ##run_experiment(numsentilabel,numtopics,alpha,beta,gamma,maxiter,5)
    #train_review, test_review, train_sentiment, test_sentiment = train_test_split(review_data.clean_sentence, review_data.sentiment_score, test_size=.25,random_state=123)
    #run_experiment(numsentilabel,numtopics,alpha,beta,gamma,maxiter,5) 
    ####LEXICON DTA
    
    '''