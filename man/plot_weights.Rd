% Generated by roxygen2: do not edit by hand
% Please edit documentation in R/plot_weights.R
\name{plot_weights}
\alias{plot_weights}
\title{Plot distribution of feature weights (weights)}
\usage{
plot_weights(
  object,
  view = 1,
  factors = 1,
  nfeatures = 10,
  color_by = NULL,
  shape_by = NULL,
  abs = FALSE,
  manual = NULL,
  color_manual = NULL,
  scale = TRUE,
  dot_size = 1,
  text_size = 5,
  legend = TRUE,
  return_data = FALSE
)
}
\arguments{
\item{object}{a \code{\link{MOFA}} object.}

\item{view}{a string with the view name, or an integer with the index of the view.}

\item{factors}{character vector with the factor name(s), or numeric vector with the index of the factor(s).}

\item{nfeatures}{number of top features to label.}

\item{color_by}{specifies groups or values (either discrete or continuous) used to color the dots (features). This can be either: 
\itemize{
\item (default) the string "group": in this case, the plot will color the dots with respect to their predefined groups.
\item a character giving the name of a feature that is present in the input data 
\item a character giving the same of a column in the features metadata slot
\item a vector of the same length as the number of features specifying the value for each feature 
\item a dataframe with two columns: "feature" and "color"
}}

\item{shape_by}{specifies groups or values (only discrete) used to shape the dots (features). This can be either: 
\itemize{
\item (default) the string "group": in this case, the plot will shape the dots with respect to their predefined groups.
\item a character giving the name of a feature that is present in the input data 
\item a character giving the same of a column in the features metadata slot
\item a vector of the same length as the number of features specifying the value for each feature 
\item a dataframe with two columns: "feature" and "shape"
}}

\item{abs}{logical indicating whether to take the absolute value of the weights.}

\item{manual}{A nested list of character vectors with features to be manually labelled (see the example for details).}

\item{color_manual}{a character vector with colors, one for each element of 'manual'}

\item{scale}{logical indicating whether to scale all weights from -1 to 1 (or from 0 to 1 if abs=TRUE).}

\item{dot_size}{numeric indicating the dot size.}

\item{text_size}{numeric indicating the text size.}

\item{legend}{logical indicating whether to add legend.}

\item{return_data}{logical indicating whether to return the data frame to plot instead of plotting}
}
\value{
A \code{\link{ggplot}} object or a \code{data.frame} if return_data is TRUE
}
\description{
An important step to annotate factors is to visualise the corresponding feature weights. \cr
This function plots all weights for a given latent factor and view, labeling the top ones. \cr
In contrast, the function \code{\link{plot_top_weights}} displays only the top features with highest loading.
}
\examples{
# Using an existing trained model on simulated data
file <- system.file("extdata", "model.hdf5", package = "MOFA2")
model <- load_model(file)

# Plot distribution of weights for Factor 1 and View 1
plot_weights(model, view = 1, factors = 1)

# Plot distribution of weights for Factors 1 to 3 and View 1
plot_weights(model, view = 1, factors = 1:3)

# Take the absolute value and highlight the top 10 features
plot_weights(model, view = 1, factors = 1, nfeatures = 10, abs = TRUE)

# Change size of dots and text
plot_weights(model, view = 1, factors = 1, text_size = 5, dot_size = 1)

}
