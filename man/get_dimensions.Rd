% Generated by roxygen2: do not edit by hand
% Please edit documentation in R/get_methods.R
\name{get_dimensions}
\alias{get_dimensions}
\title{Get dimensions}
\usage{
get_dimensions(object)
}
\arguments{
\item{object}{a \code{\link{MOFA}} object.}
}
\value{
list containing the dimensionalities of the model
}
\description{
Extract dimensionalities from the model.
}
\details{
K indicates the number of factors, D indicates the number of features, 
N indicates the (total) number of samples and M indicates the number of views.
}
\examples{
# Using an existing trained model
file <- system.file("extdata", "model.hdf5", package = "MOFA2")
model <- load_model(file)
dims <- get_dimensions(model)
}
